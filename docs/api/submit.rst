.. _api_submit:

===============================
Submit: /v1/submit (DEPRECATED)
===============================

.. deprecated:: 1.2 (2015-07-15)
   Please use the :ref:`api_geosubmit_latest` API instead.

**Purpose:** Submit data about nearby cell and WiFi networks.

.. contents::
   :local:

Request
=======

Submit requests are submitted using an HTTP POST request to one of::

    https://location.services.mozilla.com/v1/submit
    https://location.services.mozilla.com/v1/submit?key=<API_KEY>

with a JSON body containing a position report.

Here is an example position report:

.. code-block:: javascript

    {"items": [
       {
        "lat": -22.7539192,
        "lon": -43.4371081,
        "time": "2012-03-01T00:00:00.000Z",
        "accuracy": 10.0,
        "altitude": 100.0,
        "altitude_accuracy": 1.0,
        "heading": 45.0,
        "speed": 13.88,
        "radio": "gsm",
        "blue": [
            {
                "key": "ff:74:27:89:5a:77",
                "age": 2000,
                "name": "beacon",
                "signal": -110
            }
        ],
        "cell": [
            {
                "radio": "umts",
                "mcc": 123,
                "mnc": 123,
                "lac": 12345,
                "cid": 12345,
                "age": 3000,
                "signal": -60
            }
        ],
        "wifi": [
            {
                "key": "01:23:45:67:89:ab",
                "age": 2000,
                "channel": 11,
                "frequency": 2412,
                "signal": -51
            }
        ]
       }
       ]
    }


Field Definition
================

The only required fields are ``lat`` and ``lon`` and at least one Bluetooth,
cell, or WiFi entry. If neither ``lat`` nor ``lon`` are included, the record
will be discarded.

The ``altitude``, ``accuracy``, and ``altitude_accuracy`` fields are all
measured in meters. Altitude measures the height above or below the mean sea
level, as defined by WGS84.

The ``heading`` field specifies the direction of travel in
0 <= heading <= 360 degrees, counting clockwise relative to the true north.

The ``speed`` field specifies the current horizontal velocity and is measured
in meters per second.

The ``heading`` and ``speed`` fields should be omitted from the report, if the
speed and heading cannot be determined or the device was stationary while
observing the environment.

The ``time`` has to be in UTC time, encoded in ISO 8601. If not provided,
the server time will be used.


Bluetooth Fields
----------------

For ``blue`` entries, the ``key`` field is required.

key **(required)**
    The ``key`` is the mac address of the Bluetooth network. For example,
    a valid key would look similar to ``ff:23:45:67:89:ab``.

age
    The number of milliseconds since this BLE beacon was last seen.

signal
    The received signal strength (RSSI) in dBm, typically in the range of
    -10 to -127.

name
    The name of the Bluetooth network.


Cell Fields
-----------

radio
    The type of radio network. One of ``gsm``, ``umts`` or ``lte``.

mcc
    The mobile country code.

mnc
    The mobile network code.

lac
    The location area code for GSM and WCDMA networks. The tracking area
    code for LTE networks.

cid
    The cell id or cell identity.

age
    The number of milliseconds since this networks was last detected.

psc
    The primary scrambling code for WCDMA and physical cell id for LTE.

signal
    The signal strength for this cell network, either the RSSI or RSCP.

ta
    The timing advance value for this cell network.


WiFi Fields
-----------

For ``wifi`` entries, the ``key`` field is required. The client must check the
Wifi SSID for a ``_nomap`` suffix. Wifi networks with this suffix must not be
submitted to the server.

Most devices will only report the WiFi frequency or the WiFi channel,
but not both. The service will accept both if they are provided,
but you can include only one or omit both fields.

key **(required)**
    The ``key`` is the BSSID of the WiFi network. So for example
    a valid key would look similar to ``01:23:45:67:89:ab``.

    The client must check the WiFi SSID for a ``_nomap`` suffix. WiFi networks
    with this suffix must not be submitted to the server.

    WiFi networks with a hidden SSID should not be submitted to the server
    either.

age
    The number of milliseconds since this network was last detected.

frequency
    The frequency in MHz of the channel over which the client is
    communicating with the access point.

channel
    The channel is a number specified by the IEEE which represents a
    small band of frequencies.

signal
    The received signal strength (RSSI) in dBm, typically in the range of
    -51 to -113.

signalToNoiseRatio
    The current signal to noise ratio measured in dB.

ssid
    The SSID of the Wifi network. Wifi networks with a SSID ending in
    ``_nomap`` must not be collected.

Here's an example of a valid WiFi record:

.. code-block:: javascript

    {
        "key": "01:23:45:67:89:ab",
        "age": 1500,
        "channel": 11,
        "frequency": 2412,
        "signal": -51,
        "signalToNoiseRatio": 37
    }


Response
========

On successful submission, you will get a 204 status code back without
any data in the body.
