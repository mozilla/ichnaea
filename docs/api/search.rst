.. _api_search:

============
API - Search
============

Determine the current location based on provided data about
nearby cell towers or wifi base stations.

An example POST request against URL::

    https://location.services.mozilla.com/v1/search

with a JSON body:

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
                "key": "01:23:45:67:ab:cd",
            },
            {
                "key": "01:23:45:67:cd:ef",
            }
        ]
    }

The mapping can contain zero to many entries per category. At least for one
category an entry has to be provided. Empty categories can be omitted
entirely.

The top-level radio type must be one of "gsm", "cdma" or be omitted (for
example for tablets or laptops without a cell radio).

The cell specific radio entry must be one of "gsm", "cdma", "umts" or
"lte".

See :ref:`cell_records` for a detailed explanation of the cell record
fields for the different network standards.

For `wifi` entries, the `key` field is required. The client must check the
Wifi SSID for a `_nomap` suffix. Wifi's with such a suffix must not be
submitted to the server. Wifi's with a hidden SSID should not be submitted
to the server either.

The `key` is a the BSSID or MAC address of the wifi network. So for example
a valid key would look similar to `01:23:45:67:89:ab`.

For wifi lookups you need to provide at least three wifi keys of nearby wifis.
This is a industry standard that is meant to prevent you from looking up the
position of a single wifi over time.

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
