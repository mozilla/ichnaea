.. _api_geosubmit2:
.. _api_geosubmit_latest:

Geosubmit Version 2
===================

Purpose
    Submit data about nearby Bluetooth beacons, cell or WiFi networks.


Request
-------

Geosubmit requests are submitted using a POST request to the URL::

    https://location.services.mozilla.com/v2/geosubmit?key=<API_KEY>

There is an earlier :ref:`api_geosubmit` version one API, with a slightly
different and less extensive field list.

Geosubmit requests are submitted using a POST request with a JSON body:

.. code-block:: javascript

    {"items": [{
        "timestamp": 1405602028568,
        "position": {
            "latitude": -22.7539192,
            "longitude": -43.4371081,
            "accuracy": 10.0,
            "age": 1000,
            "altitude": 100.0,
            "altitudeAccuracy": 50.0,
            "heading": 45.0,
            "pressure": 1013.25,
            "speed": 3.6,
            "source": "gps"
        },
        "bluetoothBeacons": [
            {
                "macAddress": "ff:23:45:67:89:ab",
                "age": 2000,
                "name": "beacon",
                "signalStrength": -110
            }
        ],
        "cellTowers": [
            {
                "radioType": "lte",
                "mobileCountryCode": 208,
                "mobileNetworkCode": 1,
                "locationAreaCode": 2,
                "cellId": 12345,
                "age": 3000,
                "asu": 31,
                "primaryScramblingCode": 5,
                "serving": 1,
                "signalStrength": -51,
                "timingAdvance": 1
            }
        ],
        "wifiAccessPoints": [
            {
                "macAddress": "01:23:45:67:89:ab",
                "age": 5000,
                "channel": 6,
                "frequency": 2437,
                "radioType": "802.11n",
                "signalToNoiseRatio": 13,
                "signalStrength": -77
            },
            {
                "macAddress": "23:45:67:89:ab:cd"
            }
        ]
    }]}


Field Definition
----------------

Requests always need to contain a batch of :term:`reports`. Each
:term:`report` must contain at least one entry in the `bluetoothBeacons`
or `cellTowers` array or two entries in the `wifiAccessPoints` array.

Almost all of the fields are optional. For Bluetooth and WiFi records only
the `macAddress` field is required.


Global Fields
~~~~~~~~~~~~~

timestamp
    The time of observation of the data, measured in milliseconds since
    the UNIX epoch. Can be omitted if the observation time is very recent.
    The age values in each section are relative to this timestamp.


Position Fields
~~~~~~~~~~~~~~~

The position block contains information about where and when the data was
observed.

latitude
    The latitude of the observation (WSG 84).

longitude
    The longitude of the observation (WSG 84).

accuracy
    The accuracy of the observed position in meters.

altitude
    The altitude at which the data was observed in meters above sea-level.

altitudeAccuracy
    The accuracy of the altitude estimate in meters.

age
    The age of the position data (in milliseconds).

heading
    The heading field denotes the direction of travel of the device and is
    specified in degrees, where 0° ≤ heading < 360°, counting clockwise
    relative to the true north.

pressure
    The air pressure in hPa (millibar).

speed
    The speed field denotes the magnitude of the horizontal component of
    the device's current velocity and is specified in meters per second.

source
    The source of the position information. If the field is omitted, "gps"
    is assumed. The term `gps` is used to cover all types of satellite
    based positioning systems incl. Galileo and Glonass.
    Other possible values are `manual` for a position entered manually into
    the system and `fused` for a position obtained from a combination of
    other sensors or outside service queries.


Bluetooth Beacon Fields
~~~~~~~~~~~~~~~~~~~~~~~

macAddress
    The address of the Bluetooth Low Energy (BLE) beacon.

name
    The name of the BLE beacon.

age
    The number of milliseconds since this BLE beacon was last seen.

signalStrength
    The measured signal strength of the BLE beacon in dBm.


Cell Tower Fields
~~~~~~~~~~~~~~~~~

radioType
    The type of radio network. One of `gsm`, `wcdma` or `lte`.

mobileCountryCode
    The mobile country code.

mobileNetworkCode
    The mobile network code.

locationAreaCode
    The location area code for GSM and WCDMA networks. The tracking area
    code for LTE networks.

cellId
    The cell id or cell identity.

age
    The number of milliseconds since this cell was last seen.

asu
    The arbitrary strength unit indicating the signal strength if a
    direct signal strength reading is not available.

primaryScramblingCode
    The primary scrambling code for WCDMA and physical cell id for LTE.

serving
    A value of `1` indicates this as the serving cell, a value of `0`
    indicates a neighboring cell.

signalStrength
    The signal strength for this cell network, either the RSSI or RSCP.

timingAdvance
    The timing advance value for this cell tower when available.


Wifi Access Point Fields
~~~~~~~~~~~~~~~~~~~~~~~~

macAddress
    The BSSID of the Wifi network. Hidden Wifi networks must not be collected.

radioType
    The Wifi radio type, one of `802.11a`, `802.11b`, `802.11g`, `802.11n`,
    `802.11ac`.

age
    The number of milliseconds since this Wifi network was detected.

channel
    The channel is a number specified by the IEEE which represents a
    small band of frequencies.

frequency
    The frequency in MHz of the channel over which the client is
    communicating with the access point.

signalStrength
    The received signal strength (RSSI) in dBm.

signalToNoiseRatio
    The current signal to noise ratio measured in dB.

ssid
    The SSID of the Wifi network. Wifi networks with a SSID ending in
    `_nomap` must not be collected.


Response
--------

Successful requests return a HTTP 200 response with a body of an empty
JSON object.
