import json
import types
import urllib
import urllib2

from asurepo_client.http import multipart_encode
from repo.metadata import DescriptiveMetadata
import logging

LOG = logging.getLogger(__name__)

def get_property(pmap, keys, default=None):
    if type(keys) != types.ListType:  # wrap individual values
        keys = [keys]
    if len(keys) > 0:
        return get_property(pmap.get(keys[0], default), keys[1:])
    else:
        return pmap or default

def set_property(pmap, keys, val):
    if type(keys) != types.ListType:
        keys = [keys]

    if len(keys) <= 0:
        raise KeyError 
    elif len(keys) > 1:
        pmap[keys[0]] = set_property({}, keys[1:], val)
    else:
        pmap[keys[0]] = val

    return pmap

def safe_urlencode(params):
    '''
    Convert params to UTF-8 and then call urllib.urlencode (otherwise,
    urlencode may choke on the input).  Assumes that params is either a list of
    2-tuples or a dict.
    '''
    params = params or {}
    clean = lambda x: unicode(x).encode('utf-8')
    if type(params) is types.ListType:
        params = [(clean(k), clean(v)) for (k, v) in params]
    elif type(params) is types.DictType:
        params = dict([(clean(k), clean(v)) for (k, v) in params.iteritems()])
    else:
        raise ValueError('Expecting a list of 2-tuples or a dict')
    return urllib.urlencode(params)

class Action(object):
    '''
    Simple resource that stores an API reference and a URL and only needs to 
    implement a __call__ method (an appropriate call to it's URL).
    '''
    def __init__(self, api, url):
        self.api = api
        self.url = url

class Resource(object):
    '''
    Generic REST resource class that lazily loads a resource representation
    from its corresponding URL.
    '''
    def __init__(self, api, url):
        self.api = api
        self.url = url
        self._representation = None
        
    @property
    def representation(self):
        if not self._representation:
            response = self.api.open(self.url)
            rep = json.load(response)
            self._representation = rep
        return self._representation

    def delete(self):
        request = urllib2.Request(self.url)
        request.get_method = 'DELETE'
        response = self.api.open(request)
        self._representation = None

    def set_properties(self, **props):
        formdata = {}
        for propname, propvalue in props.items():
            if not isinstance(ResourceProperty, 
                              getattr(self.__class__, propname)):
                raise ValueError("Unrecognized property: %s" % propname)
            formdata['.'.join(propname)] = propvalue

        request = urllib2.Request(self.url, data=formdata)
        request.get_method = lambda: 'PUT'
        response = self.api.open(request)
        self._representation = None

    def refresh(self):
        '''
        Clear cached representation so it will be re-fetched on next call.
        '''
        self._representation = None

    def __repr__(self):
        return '<%s (%s)>' % (self.__class__.__name__, self.url)

class ResourceList(Resource):
    '''
    Base class for a resource representing a list of other resources.
    '''
    def __init__(self, api, url, resource_type):
        self._resource_type_value = resource_type
        self._resource_type = None
        self._list = None
        super(ResourceList, self).__init__(api, url)

    @property
    def resource_type(self):
        if self._resource_type is None:
            self._resource_type = load_type(self._resource_type_value)
        return self._resource_type

    def _lazy_load_list(self):
        if self._list == None:
            self._list = [self.resource_type(self.api, item_url)
                          for item_url in self.representation]
        return self._list

    def _create_new_resource(self, params=None):
        data = safe_urlencode(params or {})
        response = self.api.open(self.url, data=data)

        resp = response.read()
        resource_url = response.headers.get('Location')
        resource = self.resource_type(self.api, resource_url)
        resource._representation = json.loads(resp)
        return resource

    def __getattr__(self, attr):
        return self._lazy_load_list().__getattr__(attr)

    def __getitem__(self, item):
        return self._lazy_load_list().__getitem__(item)

    def __repr__(self):
        return '<%s[] (%s)>' % (self.resource_type.__name__, self.url)

class ResourceProperty(object):
    '''
    Property-style class for creating properties on Resource classes with some
    standard behaviors:
     - 'get' looks up @propname in the Resource's representation and returns 
        its value
     - 'set' submits a form field called @propname to the Resource's URL
        (via PUT)

    Usage:
      > class Person(Resource):
      >     first_name = ResourceProperty('firstname')
      >     last_name = ResourceProperty('lastname')
      
      > p = Person(<api>, <person_url>)
      > p.first_name
        -> returns p.representation.first_name
      > p.first_name = 'Frank'
        -> PUTs a form-encoded request to <person_url> with first_name=Frank
    '''
    def __init__(self, propname, read_only=False):
        self.propname = propname.split('.')
        self.read_only = read_only

    def __get__(self, obj, objtype=None):
        return get_property(obj.representation, self.propname)        

    def __set__(self, obj, value):
        if self.read_only:
            raise RuntimeError('Attempting to write read-only property: %s' % self.propname)
        formdata = {}
        formdata['.'.join(self.propname)] = value if value else ''
        data = safe_urlencode(formdata)
        
        request = urllib2.Request(obj.url, data=data)
        request.get_method = lambda: 'PUT'
        response = obj.api.open(request)

        if obj._representation:
            set_property(obj._representation, self.propname, value)

def load_type(type_):
    '''
    Returns a type based on the @type parameter:
     - if @type_ is already a type, just return it
     - if @type_ is a string, import and the type corresponding to it

    Sample usage:
     > load_type(dict) -> dict
     > load_type('dict') -> dict
    '''
    if type(type_) in types.StringTypes:
        split_type = type_.split('.')
        module_name = '.'.join(split_type[:-1]) or '__builtin__'
        class_name = split_type[-1]
        module = __import__(module_name, fromlist=[class_name])
        return getattr(module, class_name)
    else:
        return type_

class RelatedResource(object):
    '''
    Property-style class that retrieves a related resource whose URL is
    accessible in the defining Resource's representation via @propname and
    should be created as type @resource_type.

    Sample usage:
      class User(Resource):
         ...
    
      class BlogPost(Resource):
         creator = RelatedResource('creator', User)
         ...

      > post = BlogPost(...)
      > post.representation
        { ... , 'creator': 'http://foo.net/users/shamu', ...}
      > shamu = post.creator
      > shamu
        <User (url: 'http://foo.net/users/shamu')>
    '''

    def __init__(self, propname, resource_type):
        self.propname = propname.split('.')
        self._resource_type_value = resource_type
        self._resource_type = None

    @property
    def resource_type(self):
        if self._resource_type is None:
            self._resource_type = load_type(self._resource_type_value)
        return self._resource_type

    def __get__(self, obj, objtype=None):
        resource_url = get_property(obj.representation, self.propname)
        return self.resource_type(obj.api, resource_url)

class RelatedResourceList(RelatedResource):
    """
    Similar to RelatedResource, but creates a generic ResourceList based on the
    given @resource_type rather than creating a single Resource of that type.

    Sample usage:
      class User(Resource):
         posts = RelatedResourceList('posts', BlogPost)
         ...

      class BlogPost(Resource):
         ...

      > shamu = User(...)
      > shamu.representation
        { ... , 'posts': 'http://foo.net/users/shamu/posts', ... }
      > shamu.posts
        <Generic ResourceList of BlogPost items> 
    """

    def __get__(self, obj, objtype=None):
        resource_url = get_property(obj.representation, self.propname)
        return ResourceList(obj.api, resource_url, self.resource_type)

class ContentProperty(object):

    def __init__(self, propname):
        self.propname = propname.split('.')

    def __get__(self, obj, objtype=None):
        '''
        Load the content at @url, or return None if a 404 is encountered.
        '''
        content_url = get_property(obj.representation, self.propname)
        try:
            return obj.api.open(content_url)
        except urllib2.HTTPError as e:
            if e.code == 404:
                return None
            else:
                raise

    def __set__(self, obj, content):
        """
        Encode and send multipart body containing @content in a part named 
        'content':

          - Local filelike objects created with open() work perfectly
          - URL-based remote content can be created using the 
            create_url_content() utility method.

            >  a.content = create_url_content('http://www.example.com')

          - Other types of filelike objects can use the create_content()
            utility method to customize their values and ensure that they
            will be properly received by Django

            >  a.content = create_content(StringIO.StringIO('hello'),
                                          filename='test.txt',
                                          filetype='text/plain')
        """
        params = {'content': content}
        data, headers = multipart_encode(params)
        content_url = get_property(obj.representation, self.propname)

        request = urllib2.Request(content_url, data=data, headers=headers)
        return obj.api.open(request)

class MetadataProperty(object):

    def __init__(self, propname):
        self.propname = propname.split('.')

    def __get__(self, obj, objtype=None):
        url = get_property(obj.representation, self.propname)
        response = obj.api.open(url)
        return DescriptiveMetadata.load(response)

    def __set__(self, obj, metadata):
        '''
        Submit a JSON metadata representation to @url.
        '''
        
        metadata = DescriptiveMetadata.wrap(metadata)
        data = metadata.dumps()
        headers = {'Content-Type': 'application/json'}

        url = get_property(obj.representation, self.propname)
        request = urllib2.Request(url, data=data, headers=headers)
        response = obj.api.open(request)
        return response
