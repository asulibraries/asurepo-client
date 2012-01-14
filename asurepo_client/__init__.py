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
from repo.metadata import DescriptiveMetadata

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

class ItemDefinition(object):
    '''
    Represents a total definition of an item.  Useful for constructing an
    entire item for creating or syncing via the repository API.
    '''
    def __init__(self, 
                 label=None, 
                 metadata=None, 
                 status=None, 
                 embargo_date=None, 
                 enabled=None,
                 attachments=None):
        self.label = label
        self._metadata = metadata
        self.status = status
        self.embargo_date = embargo_date
        self.enabled = enabled  
        self.attachments = attachments or []
        

    def validate_and_transform(self):
        # truncate object label if necessary
        if len(self.label) > 255:
            self.metadata.add_notes('Original title: %s' % self.label)
            self.label = self.label[:252] + '...'

    @property
    def metadata(self):
        return self._metadata

    @metadata.setter
    def metadata(self, value): #@DuplicatedSignature
        self._metadata = DescriptiveMetadata.wrap(value)
    
    def create_item(self, collection):
        self.validate_and_transform()
        item = collection.items.new()
        if self.label:
            item.label = self.label
        if self.metadata:
            item.metadata = self.metadata
        if self.status:
            item.item_status = self.status
        if self.embargo_date:
            item.embargo_date = self.embargo_date
        if self.enabled:
            item.item_enabled = self.enabled

        for att_struct in self.attachments:
            att_struct.create_attachment(item)
        return item

    def asJson(self):
        return {
            'label': self.label,
            'metadata': self.metadata,
            'status': self.status,
            'embargo_date': self.embargo_date,
            'enabled': self.enabled,
            'attachments': [att.asJson() for att in self.attachments]
            }

    def write_directory(self, directory=None):
        if not directory:
            directory = tempfile.mkdtemp(prefix="package-")
        manifest = self.asJson()
        manifest['attachments'] = [att.write_directory(directory) 
                                   for att in self.attachments]
        manifest_path = os.path.join(directory, 'manifest.json')
        json.dump(manifest, open(manifest_path, 'w'))
        return directory

    def write_zip(self, targetfile=None):
        try:
            packagedir = tempfile.mkdtemp(prefix="package-") 
            self.write_directory(packagedir)
            return zip_directory(packagedir, targetfile)
        finally:
            shutil.rmtree(packagedir)

class AttachmentDefinition(object):

    def __init__(self, label=None, metadata=None, content=None):
        self.label = label
        self._metadata = metadata
        self.content = content

    def validate_and_transform(self):
        # truncate object label if necessary
        if len(self.label) > 255:
            self.metadata.add_notes('Original title: %s' % self.label)
            self.label = self.label[:252] + '...'

    @property
    def metadata(self):
        return self._metadata

    @metadata.setter
    def metadata(self, value): #@DuplicatedSignature
        self._metadata = DescriptiveMetadata.wrap(value)
        
    def create_attachment(self, item):
        self.validate_and_transform()
        att = item.attachments.new()
        if self.label:
            att.label = self.label
        if self.metadata:
            att.metadata = self.metadata
        if self.content:
            att.content = self.content
        return att

    def write_directory(self, directory):
        filename = os.path.basename(self.content['filename'])
        outpath = os.path.join(directory, filename)
        if os.path.exists(outpath):
            raise ValueError("The file %s already exists in the package directory" % outpath)

        with open(outpath, 'wb') as out: 
            for chunk in iter(lambda: self.content['fileobj'].read(2**16), ''): 
                out.write(chunk)

        return {
            'label': self.label,
            'metadata': self.metadata,
            'content': filename
            }
    
    def asJson(self):
        return {
            'label': self.label,
            'metadata': self.metadata,
            'content': self.content
            }


def zip_directory(directory, targetfile=None):
    '''
    Walks the contents of directory and adds them to the zipfile named by 
    targetfile (or in a temp file if targetfile is not specified).
    '''
    directory = os.path.abspath(directory)
    if not targetfile: 
        fd, targetfile = tempfile.mkstemp(prefix="package-", suffix=".zip")
        os.close(fd)

    with zipfile.ZipFile(targetfile, 'w', zipfile.ZIP_DEFLATED) as zip:
        for root, dirs, files in os.walk(directory):
            for f in files:
                abspath = os.path.join(root, f)
                relpath = os.path.relpath(abspath, directory)
                zip.write(abspath, relpath)
    return targetfile

def testzip():
    item = ItemDefinition(label="Test Item",
                          enabled=False,
                          metadata={'title': 'Test Item'})
    att = AttachmentDefinition(label="Test Attachment",
                               metadata={
                                   'contributors': [
                                       {'last': 'Hughes',
                                        'rest': 'David',
                                        'roles': ['Creator'],
                                        'is_institution': False}
                                       ]
                                },
                               content=open('/tmp/test.txt', 'r')
                              )
    item.attachments.append(att)
    return item.write_zip()
