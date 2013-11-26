from mock import Mock
import unittest
from asurepo_client import Client, Resource

TEST_TOKEN = 'faketoken'
TEST_BASE_URL = 'https://fake.com/api'


class TestResources(unittest.TestCase):

    def test_url_generation(self):
        reslist = Resource(TEST_BASE_URL, 'things', Mock())
        self.assertEqual(reslist.url, TEST_BASE_URL + '/things')
        res = reslist(2)
        self.assertEqual(res.url, TEST_BASE_URL + '/things/2')

    def test_item_class_delegation(self):

        class SubResource(Resource):
            pass

        res = Resource(TEST_BASE_URL, 'top', Mock(), item_class=SubResource)
        item_res = res(1)
        self.assertIsInstance(item_res, SubResource)

class TestClient(unittest.TestCase):

    def setUp(self):
        self.client = Client(TEST_TOKEN, TEST_BASE_URL)

    def test_session_init(self):
        auth_header = self.client.session.headers['Authorization']
        self.assertEqual(auth_header, 'Token {}'.format(TEST_TOKEN))

    def test_package_submission(self):
        col = self.client.collections(155)
        package = Mock(spec=file)
        self.client.session.post = Mock()
        col.submit_package(package)
        self.client.session.post.assert_called_with(
            col.url + '/package', data=package,
            headers={'Content-Type': 'application/zip'}
        )

if __name__ == '__main__':
    unittest.main()