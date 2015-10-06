.. _api_geolocate:
.. _api_geolocate_latest:

Geolocate
=========

Purpose
    Determine the current location based on data provided about nearby
    cell or WiFi networks and based on the IP address used to access
    the service.


Request
-------

Geolocate requests are submitted using a POST request to the URL::

    https://location.services.mozilla.com/v1/geolocate?key=<API_KEY>

This implements almost the same interface as the `Google Maps Geolocation
API <https://developers.google.com/maps/documentation/business/geolocation/>`_
endpoint, hence referred to as `GLS` or Google Location Service API. Our
service implements all of the standard GLS API with a couple of additions.

Geolocate requests are submitted using a POST request with a JSON body.

A minimal example using only WiFi networks:

.. code-block:: javascript

    {
        "wifiAccessPoints": [{
            "macAddress": "01:23:45:67:89:ab",
            "signalStrength": -51
        }, {
            "macAddress": "01:23:45:67:89:cd"
        }]
    }

A minimal example using a cell network:

.. code-block:: javascript

    {
        "cellTowers": [{
            "radioType": "wcdma",
            "mobileCountryCode": 208,
            "mobileNetworkCode": 1,
            "locationAreaCode": 2,
            "cellId": 1234567,
            "signalStrength": -60
        }]
    }

A complete example including all possible fields:

.. code-block:: javascript

    {
        "carrier": "Telecom",
        "considerIp": true,
        "homeMobileCountryCode": 208,
        "homeMobileNetworkCode": 1,
        "cellTowers": [{
            "radioType": "wcdma",
            "mobileCountryCode": 208,
            "mobileNetworkCode": 1,
            "locationAreaCode": 2,
            "cellId": 1234567,
            "age": 1,
            "psc": 3,
            "signalStrength": -60,
            "timingAdvance": 1
        }],
        "wifiAccessPoints": [{
            "macAddress": "01:23:45:67:89:ab",
            "age": 3,
            "channel": 11,
            "frequency": 2412,
            "signalStrength": -51,
            "signalToNoiseRatio": 13
        }, {
            "macAddress": "01:23:45:67:89:cd"
        }],
        "fallbacks": {
            "lacf": true,
            "ipf": true
        }
    }


Field Definition
----------------

All of the fields are optional. Though in order to get a WiFi based position
estimate at least two WiFi networks need to be provided and for each the
`macAddress` needs to be known. The minimum of two networks is a mandatory
privacy restriction for WiFi based location services.

Cell based position estimates require each cell record to contain at least
the five `radioType`, `mobileCountryCode`, `mobileNetworkCode`,
`locationAreaCode` and `cellId` values.

Position estimates do get a lot more precise if in addition to these unique
identifiers at least `signalStrength` data can be provided for each entry.

Note that all the cell JSON keys use the same names for all radio types,
generally using the official GSM name to denote similar concepts, even
though the actual client side API's might use different names for each
radio type and thus must be mapped to the JSON keys.


Global Fields
~~~~~~~~~~~~~

carrier
    The clear text name of the cell carrier / operator.

considerIp
    Should the clients IP address be used to locate it, defaults to true.

homeMobileCountryCode
    The mobile country code stored on the SIM card.

homeMobileNetworkCode
    The mobile network code stored on the SIM card.

radioType
    Same as the radioType entry in each cell record. If all the cell
    entries have the same radioType, it can be provided at the top level
    instead.


Cell Tower Fields
~~~~~~~~~~~~~~~~~

radioType
    The type of radio network. One of `gsm`, `wcdma` or `lte`.
    This is a custom extension to the GLS API, which only defines the
    top-level radioType field.

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
    The number of milliseconds since this networks was last detected.

psc
    The primary scrambling code for WCDMA and physical cell id for LTE.
    This is an addition to the GLS API.

signalStrength
    The signal strength for this cell network, either the RSSI or RSCP.

timingAdvance
    The timing advance value for this cell network.


WiFi Access Point Fields
~~~~~~~~~~~~~~~~~~~~~~~~

.. note:: Hidden WiFi networks and those whose SSID (clear text name)
          ends with the string `_nomap` must NOT be used for privacy
          reasons. It is the responsibility of the client code to filter
          these out.

macAddress
    The BSSID of the WiFi network. 

age
    The number of milliseconds since this network was last detected.

channel
    The WiFi channel, often 1 - 13 for networks in the 2.4GHz range.

frequency
    The frequency in MHz of the channel over which the client is
    communicating with the access point. This is an addition to the
    GLS API and can be used instead of the channel field.

signalStrength
    The received signal strength (RSSI) in dBm.

signalToNoiseRatio
    The current signal to noise ratio measured in dB.


Fallback Fields
~~~~~~~~~~~~~~~

The fallback section is a custom addition to the GLS API.

By default both a GeoIP based position fallback and a fallback based
on cell location areas (lac's) are enabled. Simply omit the `fallbacks`
section if you want to use the defaults. Change the values to `false`
if you want to disable either of the fallbacks.

lacf
    If no exact cell match can be found, fall back from exact cell
    position estimates to more coarse grained cell location area
    estimates, rather than going directly to an even worse GeoIP
    based estimate.

ipf
    If no position can be estimated based on any of the provided data
    points, fall back to an estimate based on a GeoIP database based on
    the senders IP address at the time of the query.

Deviations From GLS API
~~~~~~~~~~~~~~~~~~~~~~~

As mentioned in the specific fields, our API has a couple of extensions.

* Cell entries allow to specify the `radioType` per cell network
  instead of globally. This allows for example doing queries with data
  from multiple active SIM cards where one of them is on a GSM
  connection while the other uses a WCDMA connection.

* Cell entries take an extra `psc` field.

* The WiFi macAddress field takes both upper- and lower-case characters.
  It also tolerates `:`, `-` or no separator and internally strips them.

* WiFi entries take an extra `frequency` field.

* The `fallbacks` section allows some control over the more coarse
  grained position sources. If no exact match can be found, these can
  be used to return a `404 Not Found` rather than a coarse grained
  estimate with a large accuracy value.

* If either the GeoIP or location area fallbacks where used to determine
  the response, an additional fallback key will be returned in the response.

* The considerIp field has the same purpose as the fallbacks/ipf field.
  It was introduced into the GLS API later on and we continue to support
  both, with the fallbacks section taking precedence.

Response
--------

A successful response returns a position estimate and an accuracy field.
Combined these two describe the center and radius of a circle. The users
true position should be inside the circle with a 95th percentile
confidence value. The accuracy is measured in meters.

If the position is to be shown on a map and the returned accuracy is
large, it may be advisable to zoom out the map, so that all of the
circle can be seen, even if the circle itself is not shown graphically.
That way a user should still see his true position on the map and can
further zoom in.

If instead the returned position is shown highly zoomed in, the user
may just see an arbitrary location that they don't recognize at all.
This typically happens when GeoIP based results are returned and the
returned position is the center of a city or the center of a region.

A successful response will be:

.. code-block:: javascript

    {
        "location": {
            "lat": -22.7539192,
            "lng": -43.4371081
        },
        "accuracy": 100.0
    }

Should the response be based on a GeoIP estimate:

.. code-block:: javascript

    {
        "location": {
            "lat": 51.0,
            "lng": -0.1
        },
        "accuracy": 600000.0,
        "fallback": "ipf"
    }

Alternatively the fallback field can also state `lacf` for an estimate
based on a cell location area.

If no position information could be determined, a HTTP status code 404 will
be returned:

.. code-block:: javascript

    {
        "error": {
            "errors": [{
                "domain": "geolocation",
                "reason": "notFound",
                "message": "Not found",
            }],
            "code": 404,
            "message": "Not found",
        }
    }
