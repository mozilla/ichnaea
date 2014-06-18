.. _api_submit:

Submit
======

Purpose
    Submit data about nearby cell and WiFi networks.

Submit requests are submitted using a POST request to the following URL::

    https://location.services.mozilla.com/v1/submit?key=<API_KEY>

with a JSON body:

.. code-block:: javascript

    {"items": [
       {
        "lat": -22.7539192,
        "lon": -43.4371081,
        "time": "2012-03-01T00:00:00.000Z",
        "accuracy": 10,
        "altitude": 100,
        "altitude_accuracy": 1,
        "heading": 45.0,
        "speed": 13.88,
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
                "signal": -51
            }
        ]
       }
       ]
    }

Record definition
-----------------

The record fields have the same meaning and requirements as explained
in the :ref:`api_search`.

The only required fields are `lat` and `lon` and at least one cell or WiFi
entry.  If either `lat` or `lon` are not included, the record will
not be accepted.

The altitude, accuracy and altitude_accuracy fields are all measured in
meters. Altitude measures the height above or below the mean sea level,
as defined by WGS84.

The heading field specifies the direction of travel in
0 <= heading <= 360 degrees, counting clockwise relative to the true north.

The speed field specifies the current horizontal velocity and is measured
in meters per second.

The heading and speed fields should be omitted from the report, if the
speed and heading cannot be determined or the device was stationary
while observing the environment.

The time has to be in UTC time, encoded in ISO 8601. If not provided,
the server time will be used. It should be the first of the month, in
which the radio environment was observed at the given location. The
coarse grained month resolution protects the privacy of the observer.

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
