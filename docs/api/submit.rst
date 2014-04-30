.. _api_submit:

============
API - Submit
============

Submit data about nearby cell towers and wifi base stations.

An example POST request against URL::

    https://location.services.mozilla.com/v1/submit?key=<API_KEY>

with a JSON body:

.. code-block:: javascript

    {"items": [
       {
        "lat": -22.7539192,
        "lon": -43.4371081,
        "time": "2012-03-15T11:12:13.456Z",
        "accuracy": 10,
        "altitude": 100,
        "altitude_accuracy": 1,
        "radio": "gsm",
        "cell": [
            {
                "radio": "umts",
                "mcc": 123,
                "mnc": 123,
                "lac": 12345,
                "cid": 12345,
                "signal": -60
            }
        ],
        "wifi": [
            {
                "key": "01:23:45:67:89:ab",
                "channel": 11,
                "frequency": 2412,
                "signal": -50
            }
        ]
       }
       ]
    }

The fields have the same meaning as explained in the :ref:`api_search`.

The only required fields are `lat` and `lon` and at least one cell or wifi
entry.

The altitude, accuracy and altitude_accuracy fields are all measured in
meters. Altitude measures the height above or below the mean sea level,
as defined by WGS 84.

The timestamp has to be in UTC time, encoded in ISO 8601. If not
provided, the server time will be used.

On successful submission, you get a 204 status code back without any
data in the body.

If an error occurred, you get a 400 HTTP status code and a body of:

.. code-block:: javascript

    {
        "errors": {}
    }

The errors mapping contains detailed information about the errors.

For API key mismatches we still accept data. Invalid API keys will not
trigger an error.

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
