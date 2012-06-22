import json
import os
import shutil
import tempfile
import zipfile


class ItemPackager(object):
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
        self.metadata = metadata
        self.status = status
        self.embargo_date = embargo_date
        self.enabled = enabled
        self.attachments = attachments or []

    def validate_and_transform(self):
        # truncate object label if necessary
        if len(self.label) > 255:
            self.metadata.add_notes('Original title: %s' % self.label)
            self.label = self.label[:252] + '...'

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
        '''
        Write this item's manifest and any file attachments into the specified
        directory.
        '''
        if not directory:
            directory = tempfile.mkdtemp(prefix="package-")
        manifest = self.asJson()
        manifest['attachments'] = [att.write_directory(directory)
                                   for att in self.attachments]
        manifest_path = os.path.join(directory, 'manifest.json')
        json.dump(manifest, open(manifest_path, 'w'))
        return directory

    def write_zip(self, targetfile=None):
        targetfile = targetfile or tempfile.mkstemp()
        try:
            packagedir = tempfile.mkdtemp(prefix="package-")
            self.write_directory(packagedir)
            return zip_directory(packagedir, targetfile)
        finally:
            shutil.rmtree(packagedir)
        return targetfile


class AttachmentPackager(object):

    def __init__(self, label=None, metadata=None, content=None):
        self.label = label
        self.metadata = metadata
        self.content = content

    def validate_and_transform(self):
        # truncate object label if necessary
        if len(self.label) > 255:
            self.metadata.setdefault('notes', []).append('Original title: %s' % self.label)
            self.label = self.label[:252] + '...'

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
        '''
        Write content file to the given directory and return a dict describing
        the attachment, including the file it was written to.
        '''
        filename = os.path.basename(self.content['filename'])
        outpath = os.path.join(directory, filename)
        if os.path.exists(outpath):
            raise ValueError("The file %s already exists in the package directory" % outpath)

        with open(outpath, 'wb') as out:
            for chunk in iter(lambda: self.content['fileobj'].read(2 ** 16), ''):
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
