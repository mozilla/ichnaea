.. _api_geolocate:

Geolocate
=========

Purpose
    Determine the current location based on provided data about nearby
    cell or WiFi networks. This is an alternative to our
    own :ref:`api_search`.

Geolocate requests are submitted using a POST request to the URL::

    https://location.services.mozilla.com/v1/geolocate?key=<API_KEY>

Using MLS from Firefox
----------------------

This implements the same interface as the `Google Maps Geolocation
API <https://developers.google.com/maps/documentation/business/geolocation/>`_
endpoint.

You can point your Firefox Desktop browser version 24 or later at this service
by changing the `geo.wifi.uri` setting in `about:config` to::

    https://location.services.mozilla.com/v1/geolocate?key=<API_KEY>

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


Geolocate results
-----------------

Our server implements all of the standard API. At this stage it doesn't have
any limits, so you won't get any `dailyLimitExceeded` or
`userRateLimitExceeded` errors.

A successful result will be:

.. code-block:: javascript

    {
        "location": {
            "lat": 51.0,
            "lng": -0.1
        },
        "accuracy": 1200.4
    }
    

.. include:: invalid_apikey.rst
