.. _api_search:

Search
======

Purpose
    Determine the current location based on provided data about nearby
    cell or wifi networks.

Search requests are submitted using a POST request to the URL::

    https://location.services.mozilla.com/v1/search?key=<API_KEY>

A search record can contain a list of cell records and a list of WiFi
records.

A example of a well formed JSON search request :

.. code-block:: javascript

    {
        "radio": "gsm",
        "cell": [
            {
                "radio": "umts",
                "mcc": 123,
                "mnc": 123,
                "lac": 12345,
                "cid": 12345,
                "signal": -61,
                "asu": 26
            }
        ],
        "wifi": [
            {
                "key": "01:23:45:67:89:ab",
                "channel": 11,
                "frequency": 2412,
                "signal": -50
            },
            {
                "key": "01:23:45:67:ab:cd"
            },
            {
                "key": "01:23:45:67:cd:ef"
            }
        ]
    }

Record definition
-----------------

For `wifi` entries, the `key` field is required. The client must check the
Wifi SSID for a `_nomap` suffix. Wifi networks with such a suffix must not be
submitted to the server.

Most devices will only report the WiFi frequency or the WiFi channel,
but not both. The service will accept both if they are provided,
but you can include only one or omit both fields.

Valid keys for the WiFi record are:

.. include:: wifi_keys.rst

See :ref:`cell_records` for a detailed explanation of the cell record
fields for the different network standards.

Mapping records into a search request
-------------------------------------

The mapping can contain zero or more WiFi records and zero or more
cell records. If either list of records is empty, it can be omitted entirely.

For WiFi lookups you need to provide at least three WiFi keys of
nearby WiFi networks. This is an industry standard that is meant to
prevent you from looking up the position of a single WiFi over time.

Search results
--------------

.. include:: invalid_apikey.rst

A successful result will be:

.. code-block:: javascript

    {
        "status": "ok",
        "lat": -22.7539192,
        "lon": -43.4371081,
        "accuracy": 1000
    }

The latitude and longitude are numbers, with seven decimal places of
actual precision. The coordinate reference system is WGS 84. The accuracy
is an integer measured in meters and defines a circle around the location.

If no position can be determined, you instead get:

.. code-block:: javascript

    {
        "status": "not_found"
    }

If the request couldn't be processed or a validation error occurred, you
get a HTTP status code of 400 and a JSON body:

.. code-block:: javascript

    {
        "errors": {}
    }

The errors mapping contains detailed information about the errors.
