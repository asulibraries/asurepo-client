from mock import Mock, mock_open, patch
import pytest
from asurepo_client import Client, Resource

TEST_TOKEN = 'faketoken'
TEST_HOST = 'fake.com'


@pytest.fixture(scope='module')
def client():
    return Client(TEST_TOKEN, host=TEST_HOST)


def test_url_generation(client):
    base_url = client.base_url
    reslist = Resource(base_url, 'things', Mock())
    assert reslist.url == base_url + '/things'
    res = reslist(2)
    assert res.url == base_url + '/things/2'


def test_item_class_delegation(client):

    class SubResource(Resource):
        pass

    res = Resource(client.base_url, 'top', Mock(), item_class=SubResource)
    item_res = res(1)
    assert isinstance(item_res, SubResource)


def test_session_init(client):
    auth_header = client.session.headers['Authorization']
    assert auth_header == 'Token {}'.format(TEST_TOKEN)


def test_package_submission(client):
    col = client.collections(155)
    pack_name = '/tmp/pack.zip'
    client.session.post = Mock()
    m = mock_open()
    with patch('__builtin__.open', m, create=True):
        col.submit_package(pack_name)
    m.assert_called_once_with(pack_name, 'rb')
    client.session.post.assert_called_with(
        col.url + '/package', data=m(),
        headers={'Content-Type': 'application/zip'}
    )
