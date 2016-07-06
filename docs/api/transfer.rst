.. _api_transfer:
.. _api_transfer_latest:

Transfer (private)
==================

.. note::
    This is a private API for synchronizing multiple instances
    of the service and not open to the public.

Purpose
    Transfer aggregated area and station data from one instance of
    ichnaea to another.


Request
-------

Transfer requests are submitted using a POST request to the URL::

    https://location.services.mozilla.com/v1/transfer?key=<API_KEY>

The requests must contain a JSON body:

.. code-block:: javascript

    {"items": [

    ]}


Field Definition
----------------

Requests always need to contain a batch of items.


Response
--------

Successful requests return a HTTP 200 response with a body of an empty
JSON object.
