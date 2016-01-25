.. _api_geosubmit:

Geosubmit (Deprecated)
======================

.. note::
    Please use the :ref:`api_geosubmit_latest` API instead.

Purpose
    Submit data about nearby cell and WiFi networks.


Request
-------

Geosubmit requests are submitted using a POST request to the URL::

    https://location.services.mozilla.com/v1/geosubmit?key=<API_KEY>

Geosubmit requests are submitted using a POST request with a JSON body:

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


Field Definition
----------------

Requests always need to contain a batch of :term:`reports`. Each
:term:`report` must contain at least one entry in the `cellTowers` array or
two entries in the `wifiAccessPoints` array.

Most of the fields are optional. For WiFi records only the `macAddress` field
is required. For cell records, the `radioType`, `mobileCountryCode`,
`mobileNetworkCode`, `locationAreaCode` and `cellId` fields are required.

The cell record has been extended over the geolocate schema to include
three more optional fields:

age
    The number of milliseconds since this cell was primary.
    If age is 0, the cell id represents a current observation.

asu
    The arbitrary strength unit. An integer in the range of 0 to 95 (optional).

psc
    The physical cell id as an integer in the range of 0 to 503 (optional).

The WiFi record has been extended with one extra optional field
`frequency`.  Either `frequency` or `channel` may be submitted to the
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


Response
--------

Successful requests return a HTTP 200 response with a body of an empty
JSON object.
