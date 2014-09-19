from asurepo_client.packaging import Item, ItemPackager
import json
import pytest
from StringIO import StringIO
import zipfile


def test_metadata_value_helpers():
    item = Item(subject='toots')
    assert isinstance(item['subject'], list)
    assert isinstance(item['title'], list)
    with pytest.raises(KeyError):
        item['rights']
    item.add_identifier('555/eejj', 'DOI')
    assert item['identifier'][0] == dict(value='555/eejj', type='DOI')


def test_packager(tmpdir):

    item_title = 'My Packaged Item'
    subjects = ['testing', 'packaging']

    attachment_content = '<data>DATA!</data>'
    attfile = StringIO()
    attfile.write(attachment_content)
    attfile.seek(0)

    data_name = 'mydata.xml'
    data_desc = 'I have stuff'

    with ItemPackager(title=item_title) as pack:
        pack.item['subject'] = subjects
        att = pack.add_attachment(attfile, data_name)
        att.add_description(data_desc)
        pack_file = pack.write(str(tmpdir.join('mypackage')))

    assert pack_file in tmpdir.listdir()
    assert zipfile.is_zipfile(pack_file)

    with zipfile.ZipFile(pack_file) as zf:

        names = zf.namelist()
        assert 'mydata.xml' in names
        assert 'manifest.json' in names

        assert attachment_content == zf.read('mydata.xml')

        mani = json.load(zf.open('manifest.json'))
        assert item_title in mani['title']
        assert subjects == mani['subject']

        assert len(mani['attachments']) == 1

        dataentry = mani['attachments'][0]
        assert dataentry['content'] == data_name
        assert dataentry['description'][0]['value'] == data_desc
