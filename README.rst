ASU Digital Library API Client
==============================

Installation
------------

.. code-block:: bash

    $ pip install git+git://github.com/asulibraries/asurepo-client.git#egg=asurepo-client


HTTP Client
-----------

.. code-block:: pycon

    >>> from asurepo_client import Client
    >>> client = Client('YOUR_AUTHENTICATION_TOKEN')
    >>> client.collections.get().json()
    {
        "count": 80,
        "num_pages": 8,
        "per_page": 10,
        "current": 1,
        "next": "https://repository.asu.edu/api/collections?page=2",
        "previous": null,
        "results": [
            {
                "id": 155,
                "details_url": "https://repository.asu.edu/collections/155",
                "name": "Test Collection"
                ...
            }...
        ]
    }
    >>> col = client.collections(100)
    >>> col.get().json()
    {
        "id": 100
        "details_url": "https://repository.asu.edu/collections/100",
        "name": "Test Collection",
        "description": "Lots of good stuff in here."
        "url": "https://repository.asu.edu/api/collections/100"
        ...
    }
    >>> col.patch({'name': 'Changed'}).json()
    {
        "id": 100,
        "details_url": "https://repository.asu.edu/collections/100",
        "name": "Changed",
        "description": "Lots of good stuff in here."
        "url": "https://repository.asu.edu/api/collections/100"
        ...
    }

Packaging
---------

The packaging module has helpers for creating ZIP files which conform to our
packaging ingest format.

.. code-block:: python

    from asurepo_client.packaging import ItemPackager

    with ItemPackager() as pack:
        item = pack.item
        item['title'].append('Test Package Item')
        item['subject'] = ['Packaging', 'Testing']
        with open('source/att.txt') as attfile:
            att = pack.add_attachment(attfile, 'att.txt', label='My Attachment')
            att.add_identifier('555/jjj')
        pack_path = pack.write('/tmp/packages/package1')

        collection = client.collections(100)
        response = collection.submit_package(pack_path)

.. code-block:: pycon

    >>> response.header.get('location')
    http://repository.asu.edu/items/<NEW_ITEM_ID>

    >>> response.json()
    {
        title: ['Test Package Item'],
        ...
    }
