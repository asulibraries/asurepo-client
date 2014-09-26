import json
from os import path, makedirs
import shutil
import tempfile


class HasMetadata(dict):
    """Convenience dict for programmatic building of repo metadata.

    Offers defaultdict-like functionality for accessing list-value elements
    and helper methods for adding more complex and formatted elements.

    """
    string_fields = ['created', 'rights']
    list_fields = [
        'title',
        'subject',
        'description',
        'extent',
        'type',
        'contributor',
        'language',
        'notes',
        'series',
        'identifier',
        'citation',
    ]
    all_fields = list_fields + string_fields

    def __missing__(self, key):
        if key in self.list_fields:
            self[key] = val = []
            return val
        raise KeyError(key)

    def __init__(self, **kwargs):
        """Allow multi-valued fields to be initialized as a single value."""
        for f in self.list_fields:
            val = kwargs.pop(f, None)
            if val is not None and isinstance(val, (str, unicode, dict)):
                kwargs[f] = [val]
            elif isinstance(val, list):
                kwargs[f] = val
        super(HasMetadata, self).__init__(**kwargs)

    def add_description(self, val, dtype=None):
        desc = dict(value=val)
        if dtype is None:
            pass
        elif dtype in ['abstract', 'tableOfContents']:
            desc['type'] = dtype
        else:
            raise ValueError(
                'Type must be either "abstract" or "tableOfContents".')
        self['description'].append(desc)

    def add_personal_contributor(self, last, rest, roles=None):
        self._add_contributor(last, rest, roles)

    def add_institutional_contributor(self, name, roles=None):
        self._add_contributor(name, None, roles, True)

    def _add_contributor(self, last, rest=None, roles=None, institution=False):
        cont = dict(last=last)
        if rest:
            cont['rest'] = rest
        if roles:
            if isinstance(roles, (str, unicode)):
                roles = [roles]
            cont['roles'] = roles
        cont['is_institution'] = institution
        self['contributor'].append(cont)

    def add_identifier(self, ident, idtype=None):
        identifier = dict(value=ident)
        if idtype:
            identifier['type'] = idtype
        self['identifier'].append(identifier)


class Item(HasMetadata):

    def __missing__(self, key):
        if key == 'attachments':
            self[key] = val = []
            return val
        return HasMetadata.__missing__(self, key)

    def set_public(self):
        self['status'] = 'Public'

    def set_private(self):
        self['status'] = 'Private'

    def enable(self):
        self['enabled'] = True

    def disable(self):
        self['enabled'] = False

    def set_embargo_date(self, edate):
        self['embargo_date'] = edate.isoformat()

    def remove_embargo(self):
        if 'embargo_date' in self:
            del self['embargo_date']


class Attachment(HasMetadata):
    OPEN = 'OpenAcccess'
    ASU = 'ASU'
    CLOSED = 'ASU'

    def set_file_open(self):
        self['file_access'] = self.OPEN

    def set_file_asu_only(self):
        self['file_access'] = self.ASU

    def set_file_closed(self):
        self['file_access'] = self.CLOSED

    def set_derivatives_open(self):
        self['derivative_access'] = self.OPEN

    def set_derivatives_asu_only(self):
        self['derivative_access'] = self.ASU

    def set_derivatives_closed(self):
        self['derivative_access'] = self.CLOSED


class ItemPackager(object):
    """Creates a repository package.

    Helper class for building a zipfile suitable for submission to a
    collection's package endpoint. It provides new-item initialization
    and wraps writing files and the JSON manifest.

    This must be used as a context manager.

    >>> with ItemPackager() as pack:
    >>>     item = pack.item
    >>>     item['title'].append('Main Title')
    >>>     item['subject'].append('example')
    >>>     with open('./source/myfile.csv') as attfile:
    >>>         att = pack.add_attachment(attfile, 'myfile.csv', label='Data')
    >>>         att.add_description('Tabular data representing...')
    >>>     pack.write('/tmp/packages/package1')

    """

    def __init__(self, **kwargs):
        """
        Any keyword arguments will be used to initialize
        the Item's initial data/metadata (e.g. title, subject).

        """
        self.item = Item(**kwargs)
        self._working_dir = None

    def __enter__(self):
        self._working_dir = tempfile.mkdtemp(prefix="package-")
        return self

    def __exit__(self, ex_type, ex_val, traceback):
        shutil.rmtree(self._working_dir, True)
        return False

    def add_attachment(self, filehandle, package_name, **kwargs):
        """Add an attachment and associated metadata.

        Args:
            filehandle: An open file or file-like.
            package_name: Name/path within the package.
            kwargs: Attachment initialization info/metadata e.g. label

        Returns:
            An Attachement dict which can be used to add more info/metadata.

        """
        if self._working_dir is None:
            raise PackageError(
                'You can only add attachments in the context '
                'of a `with` statement.')

        package_name = package_name.lstrip('/.')
        label = kwargs.get('label')
        if not label:
            kwargs['label'] = path.basename(package_name)

        att = Attachment(**kwargs)

        outpath = path.join(self._working_dir, package_name)
        dirs = path.dirname(outpath)
        if not path.exists(dirs):
            makedirs(dirs)

        if path.exists(outpath):
            msg = '{} already exists in the package directory.'.format(outpath)
            raise PackageError(msg)

        with open(outpath, 'wb') as out:
            readcontents = lambda: filehandle.read(2 ** 16)
            for chunk in iter(readcontents, ''):
                out.write(chunk)

        att['content'] = package_name
        self.item['attachments'].append(att)
        return att

    def write(self, target):
        """Write the zip package.

        The argument `target` is the path and base name of the zipfile
        to be created. The .zip extension will be appended. Given
        `/tmp/packages/package1` the resulting ZIP file will be located at
        `/tmp/packages/package1.zip`.

        """
        mpath = path.join(self._working_dir, 'manifest.json')
        with open(mpath, 'w') as mani:
            json.dump(self.item, mani)
        return shutil.make_archive(target, 'zip', self._working_dir)


class PackageError(Exception):
    pass
