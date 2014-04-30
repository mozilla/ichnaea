.. _api_geolocate:

===============
API - Geolocate
===============

Determine the current location based on provided data about
nearby cell towers or wifi base stations. This is an alternative to our own
:ref:`api_search`.

Do a POST request against the URL::

    https://location.services.mozilla.com/v1/geolocate?key=<API_KEY>

This implements the same interface as the `Google Maps Geolocation
API <https://developers.google.com/maps/documentation/business/geolocation/>`_
endpoint.

You can point your Firefox Desktop browser version 24 or later at this service
by changing the `geo.wifi.uri` setting in `about:config` to::

    https://location.services.mozilla.com/v1/geolocate?key=<API_KEY>

Our service doesn't yet specify the format or how to get an API key. Simply
use any kind of byte string, for example a uuid.

This only works if your version of Firefox already uses the new Google
Geolocation API. If you reset the settings value it should have been::

    https://www.googleapis.com/geolocation/v1/geolocate?key=%GOOGLE_API_KEY%

If you see a different value, please update to Firefox 24 or later.

Our server implements all of the standard API. At this stage it doesn't have
any limits, so you won't get any `dailyLimitExceeded`
or `userRateLimitExceeded` errors.

For API key mismatches we return a `keyInvalid` message with an HTTP
400 error.  The JSON response should be:

.. code-block:: javascript

    {
        "error": {
            "errors": [{
                "domain": "usageLimits",
                "reason": "keyInvalid",
                "message": "No API key was found",
            }],
            "code": 400,
            "message": "No API key",
        }
    }

