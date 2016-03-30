.. _api_search:

Search (Deprecated)
===================

.. note::
    Please use the :ref:`api_geolocate_latest` API instead.

Purpose
    Determine the current location based on data provided about nearby
    Bluetooth, cell or WiFi networks and based on the IP address used
    to access the service.


Request
-------

Search requests are submitted using a POST request to the URL::

    https://location.services.mozilla.com/v1/search?key=<API_KEY>

A search record can contain a list of Bluetooth, cell and WiFi records.

A example of a well formed JSON search request :

.. code-block:: javascript

    {
        "radio": "gsm",
        "blue": [
            {
                "key": "ff:23:45:67:89:ab",
                "age": 1000,
                "signal": -110
            },
            {
                "key": "ff:23:45:67:89:cd",
                "signal": -105
            }
        ],
        "cell": [
            {
                "radio": "umts",
                "mcc": 123,
                "mnc": 123,
                "lac": 12345,
                "cid": 12345,
                "signal": -61,
                "age": 1500,
                "asu": 26
            }
        ],
        "wifi": [
            {
                "key": "01:23:45:67:89:ab",
                "age": 3000,
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


Field Definition
----------------

Bluetooth Fields
~~~~~~~~~~~~~~~~

For `blue` entries, the `key` field is required.

key **(required)**
    The `key` is the mac address of the Bluetooth network. So for example
    a valid key would look similar to `ff:23:45:67:89:ab`.

age
    The number of milliseconds since this BLE beacon was last seen.

signal
    The received signal strength (RSSI) in dBm, typically in the range of
    -10 to -127.

name
    The name of the Bluetooth network.


Cell Fields
~~~~~~~~~~~

radio
    The type of radio network. One of `gsm`, `umts` or `lte`.

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
~~~~~~~~~~~

For `wifi` entries, the `key` field is required. The client must check the
Wifi SSID for a `_nomap` suffix. Wifi networks with such a suffix must not be
submitted to the server.

Most devices will only report the WiFi frequency or the WiFi channel,
but not both. The service will accept both if they are provided,
but you can include only one or omit both fields.

key **(required)**
    The client must check the WiFi SSID for a `_nomap`
    suffix. WiFi networks with such a suffix must not be submitted to the
    server. WiFi networks with a hidden SSID should not be submitted to the
    server either.

    The `key` is the BSSID of the WiFi network. So for example
    a valid key would look similar to `01:23:45:67:89:ab`.

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
    `_nomap` must not be collected.

An example of a valid WiFi record is below:

.. code-block:: javascript

    {
        "key": "01:23:45:67:89:ab",
        "age": 1500,
        "channel": 11,
        "frequency": 2412,
        "signal": -51,
        "signalToNoiseRatio": 37
    }


Mapping records into a search request
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The mapping can contain zero or more Bluetooth records, zero or more WiFi
records and zero or more cell records. If any list of records is empty,
it can be omitted entirely.

For Bluetooth and WiFi lookups at least two keys of nearby networks need
to be provided. This is an industry standard that is meant to prevent you
from looking up the position of a single network over time.


Response
--------

A successful response will be:

.. code-block:: javascript

    {
        "status": "ok",
        "lat": -22.7539192,
        "lon": -43.4371081,
        "accuracy": 100.0
    }

The latitude and longitude are numbers, with seven decimal places of
actual precision. The coordinate reference system is WGS 84. The accuracy
is an integer measured in meters and defines a circle around the location.

Should the response be based on a GeoIP estimate:

.. code-block:: javascript

    {
        "status": "ok",
        "lat": 51.0,
        "lon": -0.1,
        "accuracy": 600000.0,
        "fallback": "ipf"
    }

Alternatively the fallback field can also state `lacf` for an estimate
based on a cell location area.

If no position can be determined, you instead get:

.. code-block:: javascript

    {
        "status": "not_found"
    }
