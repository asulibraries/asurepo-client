import json
import os
import shutil
import tempfile
import types
import uuid
import zipfile


class ItemPackager(object):
    """
    Represents a total definition of an item.  Useful for constructing an
    entire item for creating or syncing via the repository API.

    """
    def __init__(self, label=None, metadata=None, status=None,
                 embargo_date=None, enabled=None, attachments=None):
        self.label = label
        self.metadata = metadata or {}
        self.status = status
        self.embargo_date = embargo_date
        self.enabled = enabled
        self.attachments = attachments or []

    def validate_and_transform(self):
        # truncate object label if necessary
        if len(self.label) > 255:
            self.metadata.add_notes('Original title: %s' % self.label)
            self.label = self.label[:252] + '...'

    def as_json(self):
        self.validate_and_transform()
        return {
            'label': self.label,
            'metadata': self.metadata,
            'status': self.status,
            'embargo_date': self.embargo_date.isoformat()
                            if self.embargo_date else None,
            'enabled': self.enabled,
            'attachments': [att.as_json() for att in self.attachments]
        }

    def write_directory(self, directory=None):
        """
        Write this item's manifest and any file attachments into the specified
        directory.

        """
        if not directory:
            directory = tempfile.mkdtemp(prefix="package-")
        manifest = self.as_json()
        manifest['attachments'] = [att.write_directory(directory)
                                   for att in self.attachments]
        manifest_path = os.path.join(directory, 'manifest.json')
        json.dump(manifest, open(manifest_path, 'w'))
        return directory

    def write_zip(self, targetfile):
        try:
            packagedir = tempfile.mkdtemp(prefix="package-")
            self.write_directory(packagedir)
            return zip_directory(packagedir, targetfile)
        finally:
            shutil.rmtree(packagedir)
        return targetfile


def zip_directory(directory, targetfile=None):
    """
    Walks the contents of directory and adds them to the zipfile named by
    targetfile (or in a temp file if targetfile is not specified).

    """
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


class AttachmentPackager(object):

    def __init__(self, label=None, metadata=None, fileobj=None, filename=None):
        self.label = label
        self.metadata = metadata or {}
        self.fileobj = fileobj
        if fileobj and not filename:
            name = None
            if (hasattr(fileobj, 'name') and
                isinstance(fileobj.name, types.StringTypes)):
                name = os.path.basename(fileobj.name)
            self.filename = name if name else uuid.uuid4()
        else:
            self.filename = filename

    def validate_and_transform(self):
        # truncate object label if necessary
        if len(self.label) > 255:
            orig_title = 'Original title: %s' % self.label
            self.metadata.setdefault('notes', []).append(orig_title)
            self.label = self.label[:252] + '...'

    def write_directory(self, directory):
        """
        Write content file to the given directory and return a dict describing
        the attachment, including the file it was written to.

        """
        if self.fileobj:
            outpath = os.path.join(directory, self.filename)
            if os.path.exists(outpath):
                raise ValueError(
                    "The file %s already exists in the "
                    "package directory." % outpath)

            with open(outpath, 'wb') as out:
                readcontents = lambda: self.fileobj.read(2 ** 16)
                for chunk in iter(readcontents, ''):
                    out.write(chunk)
                self.fileobj.close()

        return self.as_json()

    def as_json(self):
        self.validate_and_transform()
        return {
            'label': self.label,
            'metadata': self.metadata,
            'content': self.filename if self.fileobj else None
        }


class BatchIngest(object):
    """
    Controls submission of a set of zip packages into the given collection.

    """

    def __init__(self, collection, packages):
        """
        Args:
            collection: Collection resource obtained from asurepo_client.Client
            packages: list of paths to the zip packages to submit

        """
        self.collection = collection
        self.packages = packages
        self.errors = []
        self.successes = []

    def run(self):
        for zip_path in self.packages:
            self.ingest(zip_path)

    def retry_failed(self, err_type=Exception):
        """
        Helpful when running in a REPL where you have the chance to
        inspect the errors and make some adjustments, or if there were
        uncontrollable conditions like network hiccoughs.

        Args:
            err_type: class of the error type to retry

        """
        retry = [pack for pack, err in self.errors if isinstance(err, err_type)]
        self.errors = [
            (pack, err) for pack, err in self.errors if pack not in retry
        ]
        for pack in retry:
            self.ingest(pack)

    def ingest(self, package_path):
        """Try to submit the package.

        On success, adds (path, url) tuple to the success list. On any
        exception, adds (path, traceback) to the errors list.

        """
        try:
            with open(package_path, 'rb') as zip_in:
                resp = self.collection.submit_package(zip_in)
            resp.raise_for_status()
            if resp.status_code == 201:
                loc = resp.headers['location']
                self.successes.append((package_path, loc))
            else:
                raise ValueError(
                    'Unexpected API status {}'.format(resp.status_code)
                )
        except Exception as e:
            self.errors.append((package_path, e))
