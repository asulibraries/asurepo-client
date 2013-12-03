from mock import Mock, patch, mock_open
import unittest
from requests.exceptions import ConnectionError, HTTPError
from asurepo_client import Client, Resource, Collection
from asurepo_client.packaging import BatchIngest

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


@patch('__builtin__.open', mock_open(), create=True)
class TestBatchIngest(unittest.TestCase):
    SAMPLE_URL = 'http://example.com'

    def setUp(self):
        self.collection = Mock(spec=Collection)
        self.successful_response = Mock()
        self.successful_response.status_code = 201
        self.successful_response.headers = {'location': self.SAMPLE_URL}

    def test_run(self):
        packages = ['1.zip', '2.zip']
        self.collection.submit_package = Mock(
            side_effect=[self.successful_response, self.successful_response]
        )
        batch = BatchIngest(self.collection, packages)
        batch.run()
        self.assertEqual(len(batch.successes), 2)
        self.assertEqual(len(batch.errors), 0)
        for path, url in batch.successes:
            self.assertEqual(url, self.SAMPLE_URL)

    def test_retry_failures(self):
        packages = ['1.zip', 'malformed.zip', 'networkerr.zip']
        self.collection.submit_package = Mock(
            side_effect=[
                self.successful_response,
                HTTPError('Malformed Package'),
                ConnectionError('Where is the server?')
            ]
        )
        batch = BatchIngest(self.collection, packages)
        batch.run()
        self.assertEqual(len(batch.successes), 1)
        self.assertEqual(len(batch.errors), 2)
        self.collection.submit_package = Mock(
            side_effect=[self.successful_response]
        )
        batch.retry_failed(ConnectionError)
        self.assertEqual(len(batch.successes), 2)
        self.assertEqual(len(batch.errors), 1)


if __name__ == '__main__':
    unittest.main()