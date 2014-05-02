.. _api_submit:

Submit
======

Purpose
    Submit data about nearby cell towers and wifi base stations.

Submit requests are submitted using a POST request to the following URL::

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

Record definition
-----------------

The record fields have the same meaning and requirements as explained
in the :ref:`api_search`.

The only required fields are `lat` and `lon` and at least one cell or wifi
entry.  If either `lat` or `lon` are not included, the record will
not be accepted.

The altitude, accuracy and altitude_accuracy fields are all measured in
meters. Altitude measures the height above or below the mean sea level,
as defined by WGS84.

The timestamp has to be in UTC time, encoded in ISO 8601. If not
provided, the server time will be used.

Submit results
--------------

On successful submission, you will get a 204 status code back without
any data in the body.

If an error occurred, you get a 400 HTTP status code and a body of:

.. code-block:: javascript

    {
        "errors": {}
    }

The errors mapping contains detailed information about the errors.

Note that the submit API will **not** reject data for invalid API keys.
