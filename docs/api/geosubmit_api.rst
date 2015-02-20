.. _api_geosubmit:

Geosubmit
=========

Purpose
    Submit data about nearby cell and WiFi networks.

Geosubmit requests are submitted using a POST request to the URL::

    https://location.services.mozilla.com/v1/geosubmit?key=<API_KEY>


Geosubmit upload format
-----------------------

Geosubmit requests are submitted using a POST request with a JSON
body:

.. code-block:: javascript

    {"items": [
       {
        "latitude": -22.7539192,
        "longitude": -43.4371081,
        "accuracy": 10.0,
        "altitude": 100.0,
        "altitudeAccuracy": 50.0,
        "timestamp": 1405602028568,
        "heading": 45.0,
        "speed": 3.6,
        "cellTowers": [
            {
                "radioType": "gsm",
                "cellId": 12345,
                "locationAreaCode": 2,
                "mobileCountryCode": 208,
                "mobileNetworkCode": 1,
                "age": 3,
                "asu": 31,
                "signalStrength": -51,
                "timingAdvance": 1
            }
        ],
        "wifiAccessPoints": [
            {
                "macAddress": "01:23:45:67:89:ab",
                "age": 3,
                "channel": 6,
                "frequency": 2437,
                "signalToNoiseRatio": 13,
                "signalStrength": -77
            },
            {
                "macAddress": "23:45:67:89:ab:cd"
            }
        ]
       }
    ]}

Record definition
-----------------

Requests always need to contain a batch of reports. Each report
must contain at least one entry in the `cellTowers` array or
two entries in the `wifiAccessPoints` array.

Most of the fields are optional. For WiFi records only the `macAddress` field
is required. For cell records, the `radioType`, `mobileCountryCode`,
`mobileNetworkCode`, `locationAreaCode` and `cellId` fields are required.

The cell record has been extended over the geolocate schema to include
two more optional fields:

psc
    The physical cell id as an integer in the range of 0 to 503 (optional).

asu
    The arbitrary strength unit. An integer in the range of 0 to 95 (optional).

The WiFi record has been extended with one extra optional field
`frequency`.  Either `frequency` or `channel` maybe submitted to the
geosubmit API as they are functionally equivalent.

frequency
    The frequency in MHz of the channel over which the client is
    communicating with the access point.


The top level schema is identical to the geolocate schema with the
following additional fields:

latitude
    The latitude of the observation (WSG 84).

longitude
    The longitude of the observation (WSG 84).

timestamp
    The time of observation of the data, measured in milliseconds since
    the UNIX epoch. Should be omitted if the observation time is very
    recent.

accuracy
    The accuracy of the observed position in meters.

altitude
    The altitude at which the data was observed in meters above sea-level.

altitudeAccuracy
    The accuracy of the altitude estimate in meters.

heading
    The heading field denotes the direction of travel of the device and is
    specified in degrees, where 0° ≤ heading < 360°, counting clockwise
    relative to the true north. If the device cannot provide heading
    information or the device is stationary, the field should be omitted.

speed
    The speed field denotes the magnitude of the horizontal component of
    the device's current velocity and is specified in meters per second.
    If the device cannot provide speed information, the field should be
    omitted.


Geosubmit results
-----------------

Successful requests return a HTTP 200 response with a body of an empty
JSON object.

Geosubmit results can return the same error results as those used by the
:ref:`api_geolocate` API endpoint.

You might also get a 5xx HTTP response if there was a service side problem.
This might happen if the service or some key part of it is unavailable.
If you encounter a 5xx response, you should retry the request at a later
time. As a service side problem is unlikely to be resolved immediately,
you should wait a couple of minutes before retrying the request for the
first time and a couple of hours later if there's still a problem.
