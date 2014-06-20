.. _api_geolocate:

Geosubmit
=========

Purpose
    Determine the current location based on provided data about nearby
    cell or WiFi networks. This is a fully backwards compatible
    extension to the :ref:`api_geolocate` api.

    The extensions that geosubmit implement allow clients to submit
    addional location data to the geosubmit API that will be added to
    the Mozilla Location Service.

Geosubmit requests are submitted using a POST request to the URL::

    https://location.services.mozilla.com/v1/geosubmit?key=<API_KEY>

Using MLS from Firefox
----------------------

This implements a backwards compatible interface as the `Google Maps Geolocation
API <https://developers.google.com/maps/documentation/business/geolocation/>`_
endpoint.

You can point your Firefox Desktop browser version 24 or later at this service
by changing the `geo.wifi.uri` setting in `about:config` to::

    https://location.services.mozilla.com/v1/geosubmit?key=<API_KEY>

If you are using an official Mozilla build of Firefox you can use
`%GOOGLE_API_KEY%` (including the percent signs) as the API key. We have
whitelisted Mozilla's official Google key to also work for our location
service.

If you only want to do a short test of the functionality, you can currently
also use a key of `test`.

This only works if your version of Firefox already uses the new Google
Geolocation API. If you reset the settings value it should have been::

    https://www.googleapis.com/geolocation/v1/geolocate?key=%GOOGLE_API_KEY%

If you see a different value, please update to Firefox 24 or later.


Geosubmit upload format
-----------------------

Geosubmit requests are submitted using a POST request with a JSON
body:

.. code-block:: javascript

       {
        "latitude": -22.7539192,
        "longitude": -43.4371081,
        "accuracy": 10,
        "altitude": 100,
        "radioType": "gsm",
        "cellTowers": [
            {
                "cellId": 12345,
                "locationAreaCode": 2,
                "mobileCountryCode": 208,
                "mobileNetworkCode": 1,
                "age": 3
            }
        ],
        "wifi": [
            {
                "macAddress": "01:23:45:67:89:ab",
                "signalStrength": 5,
                "age": 3,
                "channel": 11,
                "signalToNoiseRatio": -51
            }
        ]
       }

Record definition
-----------------

Records must contain at least one of the `wifi` list of wifi access points or the `cellTowers` list of cellular tower records. 

The minimum requirements for the `WifiAccessPointSchema` and the `CellTowerSchema` are identical to the geolocate API.

The `CellTowerSchema` has been extended to include two more optional
fields:

psc
    The physical cell id as an integer in the range of 0 to 503 (optional).

asu
    The arbitrary strength unit. An integer in the range of 0 to 95 (optional).
    The formula: ``RSRP [dBm] = ASU – 140``.

The `WifiAccessPointSchema` record has been extended with one extra
optional field `frequency`.  Either `frequency` or `channel` maybe
submitted to the geosubmit API as they are functionally equivalent.

frequency
    The frequency in MHz of the channel over which the client is
    communicating with the access point.


The top level `GeosubmitSchema` is identical to the `GeolocateSchema`
with the folowing addtional fields:

latitude
    This is mapped to `latitude` in the :ref:`api_submit` API.

longitude
    This is mapped to `longitude` in the :ref:`api_submit` API.

timestamp
    This is mapped to `timestamp` in the :ref:`api_submit` API.

accuracy
    This is mapped to `accuracy` in the :ref:`api_submit` API.

altitude
    This is mapped to `altitude` in the :ref:`api_submit` API.

altitudeAccuracy
    This is the same as `altitude_accuracy` in the :ref:`api_submit` API.

heading
    The heading attribute denotes the direction of travel of the hosting device and is specified in degrees, where 0° ≤ heading < 360°, counting clockwise relative to the true north. If the implementation cannot provide heading information, the value of this attribute must be null. If the hosting device is stationary (i.e. the value of the speed attribute is 0), then the value of the heading attribute must be NaN.

speed
    The speed attribute denotes the magnitude of the horizontal component of the hosting device's current velocity and is specified in meters per second. If the implementation cannot provide speed information, the value of this attribute must be null. Otherwise, the value of the speed attribute must be a non-negative real number. 

Batch uploads where multiple sets of lat/long pairs and wifi and cell
data are supported by using an 'items' at the top level of the JSON
blob:

.. code-block:: javascript

    {"items": [
       {
        "latitude": -22.7539192,
        "longitude": -43.4371081,
        "accuracy": 10,
        "altitude": 100,
        "radioType": "gsm",
        "cellTowers": [
            {
                "cellId": 12345,
                "locationAreaCode": 2,
                "mobileCountryCode": 208,
                "mobileNetworkCode": 1,
                "age": 3
            }
        ],
        "wifi": [
            {
                "macAddress": "01:23:45:67:89:ab",
                "signalStrength": 5,
                "age": 3,
                "channel": 11,
                "signalToNoiseRatio": -51
            }
        ]
       }
       ]
    }

Geosubmit results
-----------------

If a standard geolocate call is made to the geosubmit API, the result
will always be identical to the same call made on the :ref:`api_geolocate`
API endpoint.

For geosubmit uploads where the batch mode is used, the result will
always be an empty JSON dictionary.

.. include:: invalid_apikey.rst
