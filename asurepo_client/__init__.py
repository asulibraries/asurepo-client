import json
import requests


class Resource(object):
    """
    Representation of an HTTP resource. This provides helper methods for
    executing HTTP verbs against the specified resource.

    """

    def __init__(self, base_url, name, session, item_class=None):
        self.base_url = base_url.strip('/')
        self.name = name
        self.url = '{}/{}'.format(self.base_url, name)
        self.session = session
        self.item_class = (
            item_class or getattr(self, '_item_class', None) or self.__class__
        )

    def __call__(self, resource_id):
        """
        Returns a new resource based off of the base_url of self. This allows
        us to get nested resources. E.g.

        >>> list_of_items = client.items
        >>> list_of_items.url https://base.url/api/items
        >>> individual_item = client.items(45)
        >>> individual_item.url
        https://base.url/api/items/45

        If a subclass is passed item_class in the constructor or if the
        '_item_class' attribute is set, this class will be used in
        place of self.__class__

        """
        if not resource_id:
            return self
        return self.item_class(self.url, resource_id, self.session)

    def post(self, data, **kwargs):
        resp = self.session.post(self.url, data=json.dumps(data), **kwargs)
        return self.process(resp)

    def get(self, params=None, **kwargs):
        resp = self.session.get(self.url, params=params, **kwargs)
        return self.process(resp)

    def put(self, data, **kwargs):
        resp = self.session.put(self.url, data=json.dumps(data), **kwargs)
        return self.process(resp)

    def delete(self, **kwargs):
        resp = self.session.delete(self.url, **kwargs)
        return self.process(resp)

    def patch(self, data, **kwargs):
        resp = self.session.patch(self.url, data=json.dumps(data), **kwargs)
        return self.process(resp)

    def options(self, **kwargs):
        resp = self.session.options(self.url, **kwargs)
        return self.process(resp)

    def process(self, response):
        """TODO: Maybe do something here. Like wrap HTTP exceptions?"""
        return response


class Collection(Resource):

    def submit_package(self, package_path):
        url = self.url + '/package'
        headers = {'Content-Type': 'application/zip'}
        with open(package_path, 'rb') as package:
            return self.session.post(url, data=package, headers=headers)


class Client(object):
    """
    Entry point to the ASU Digital Repository API. Users must specify a
    valid token.

    """

    def __init__(self, token, host=None, verify_ssl=True):
        """
        This sets up the client-exposed API resources and initializes an
        HTTP session with default/required state.

        """
        self.base_url = 'https://{}/api'.format(host or 'repository.asu.edu')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Authorization': 'Token {}'.format(token),
            'Accept': 'application/json',
            'User-Agent': 'asurepo-client v{}'.format(__version__)
        })
        self.session.verify = verify_ssl
        self.collections = self.register_resource(
            'collections', item_class=Collection
        )

    def register_resource(self, name, cls=None, item_class=None):
        cls = cls or Resource
        return cls(self.base_url, name, self.session, item_class)
