'''
Client for retrieving and manipulating digital objects in the ASU digital
repository via its REST API.
'''

import cookielib
import filelike
import httplib
import json
import logging
import mimetypes
import os
import posixpath
import poster
import shutil
import tempfile
import urllib
import urllib2
import urlparse
import zipfile

from asurepo_client.rest import (Resource, Action, ResourceList,
    ResourceProperty, RelatedResource, MetadataProperty,
    ContentProperty)

LOG = logging.getLogger('asurepo.client')

ref = lambda cls_name: '%s.%s' % (__name__, cls_name)

#----------------{Main API entry point}----------------------
class BaseAPI(Resource):

    collections = RelatedResource('resources.collections', ref('Collections'))
    items = RelatedResource('resources.objects', ref('Items'))
    attachments = RelatedResource('resources.attachments', ref('Attachments'))
    commit = RelatedResource('resources.commit', ref('CommitAction'))
    rollback = RelatedResource('resources.rollback', ref('RollbackAction'))

    def __init__(self, apiroot):
        self.apiroot = apiroot
        self.opener = self.create_opener()
        super(BaseAPI, self).__init__(self, apiroot)

    def open(self, *args, **kwargs):
        return self.opener.open(*args, **kwargs)

    def __getstate__(self):
        return {'apiroot': self.apiroot}

    def __setstate__(self, state):
        self.__init__(state.get('apiroot'))

class BasicAuthAPI(BaseAPI):
    def __init__(self, apiroot, username, password):
        self.username = username
        self.password = password
        super(BasicAuthAPI, self).__init__(apiroot)

    def create_opener(self):
        _, netloc, _, _, _, _ = urlparse.urlparse(self.apiroot)
        self.password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        self.password_manager.add_password(None, netloc,
                                           self.username, self.password)

        handlers = [
                poster.streaminghttp.StreamingHTTPHandler,
                poster.streaminghttp.StreamingHTTPRedirectHandler,
                urllib2.HTTPCookieProcessor(cookielib.CookieJar()),
                urllib2.HTTPBasicAuthHandler(self.password_manager)
                ]
        if hasattr(httplib, "HTTPS"):
            handlers.append(poster.streaminghttp.StreamingHTTPSHandler)

        return urllib2.build_opener(*handlers)

    def __getstate__(self):
        return {
            'apiroot': self.apiroot,
            'username': self.username,
            'password': self.password
            }

    def __setstate__(self, state):
        self.__init__(state.get('apiroot'),
                      state.get('username'),
                      state.get('password'))

# add alias
API = BasicAuthAPI

#----------------{Resource list types}----------------------
class Collections(ResourceList):

    def __init__(self, api, url):
        return super(Collections, self).__init__(api, url, ref('Collection'))

    def new(self, name, description=None):
        params = {'name': name}
        if description is not None:
            params['description'] = description
        return self._create_new_resource(params)

class Items(ResourceList):

    def __init__(self, api, url):
        return super(Items, self).__init__(api, url, ref('Item'))

    def new(self, collection_url=None):
        params = {'collection': collection_url} if collection_url else {}
        return self._create_new_resource(params)

class Attachments(ResourceList):

    def __init__(self, api, url):
        return super(Attachments, self).__init__(api, url, ref('Attachment'))

    def new(self):
        # please do not touch the magic foobar
        return self._create_new_resource({'foo':'bar'})


#----------------{Individual Resource types}----------------------
class Collection(Resource):

    name = ResourceProperty('name')
    description = ResourceProperty('description')
    persistent_url = ResourceProperty('persistent_url', read_only=True)
    items = RelatedResource('items', ref('Items'))

class Item(Resource):

    collection = RelatedResource('collection', ref('Collection'))
    label = ResourceProperty('label')
    attachments = RelatedResource('attachments', ref('Attachments'))
    metadata = MetadataProperty('metadata')
    status = ResourceProperty('status', read_only=True)
    item_status = ResourceProperty('item_status')
    embargo_date = ResourceProperty('embargo_date')
    enabled = ResourceProperty('enabled', read_only=True)
    item_enabled = ResourceProperty('item_enabled')
    persistent_url = ResourceProperty('persistent_url', read_only=True)

class Attachment(Resource):
    label = ResourceProperty('label')
    status = ResourceProperty('status')
    item = RelatedResource('item', ref('Item'))
    metadata = MetadataProperty('metadata')
    content = ContentProperty('content')
    persistent_url = ResourceProperty('persistent_url', read_only=True)

class CommitAction(Action):
    def __call__(self, force=False):
        data = urllib.urlencode({'force': 'true' if force else 'false'})
        response = self.api.open(self.url, data=data)

class RollbackAction(Action):
    def __call__(self):
        response = self.api.open(self.url, data='')

#-------------{Content creation helper functions}----------------
def create_url_content(url, filename=None, opener=None):
    '''
    Utility function that creates content appropriate for assigning Attachment's
    @content property (based on the content at @url).  If provided, a custom
    urllib2.OpenerDirector will be used to open the URL.
    '''
    openfun = urllib2.urlopen if opener is None else opener.open
    fileobj = openfun(url)
    filename = filename or filename_from_url(url)
    filetype = fileobj.headers.get('content-type')

    fileobj = filelike.wrappers.Buffer(fileobj)  # wrap for seek()
    return create_content(fileobj, filename=filename, filetype=filetype)

def create_content(fileobj, filename=None, filetype=None):
    '''
    Utility method for creating content appropriate for assigning to
    Attribute's @content property.  This ensures that filename is specified
    (which Django needs to recognize a multipart/form-encoded part as a file)
    and does its best to guess the filetype if none is provided.
    '''
    filename = filename or 'content'
    if not filetype and filename:
        filetype = mimetypes.guess_type(filename)[0]
    return {'filename': filename, 'filetype': filetype, 'fileobj': fileobj}

def filename_from_url(url):
    _, _, path, _, _ = urlparse.urlsplit(url)
    return posixpath.basename(path)
