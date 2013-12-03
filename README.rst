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

    packager = ItemPackager(
        label='Test Package Item',
        metadata={
            'subject': ['Packaging']
        }
    )

    packager.attachments.append(AttachmentPackager(
        label='Example Image',
        fileobj=open('test.jpg') # your filelike will be closed
    ))

    zipfile = packager.write_zip('/tmp/item.zip')
    collection = client.collections(100)
    response = collection.submit_package(zipfile)

.. code-block:: pycon

    >>> response.header.get('location')
    http://repository.asu.edu/items/<NEW_ITEM_ID>

    >>> response.json()
    {
        label: 'Test Package Item'
        ...
    }

Ingesting Packages
~~~~~~~~~~~~~~~~~~

Included in the packaging module is the helper class BatchIngest which
manages submitting a set of packages.

.. code-block:: pycon

    >>> col = client.collections(100)
    >>> batch = BatchIngest(col, glob('packages/*.zip'))
    >>> batch.run()
    >>> batch.successes
    [
        ('packages/1.zip', 'http://repository.asu.edu/api/items/<NEW_ID>')
        ('packages/2.zip', 'http://repository.asu.edu/api/items/<NEW_ID>')
        ('packages/3.zip', 'http://repository.asu.edu/api/items/<NEW_ID>')
        ...
    ]
    >>> batch.errors
    [
        ('packages/5.zip', ConnectionError('network unavailable')),
        ('packages/6.zip', IOError('file not found'))
    ]
    >>> batch.retry_failed(ConnectionError)
    >>> batch.errors
    [
        ('packages/6.zip', IOError('file not found'))
    ]


