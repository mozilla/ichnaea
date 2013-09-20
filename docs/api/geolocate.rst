.. _api_geolocate:

===============
API - Geolocate
===============

Determine the current location based on provided data about
nearby cell towers or wifi base stations. This is an alternative to our own
:ref:`api_search`.

Do a POST request against the URL::

    /v1/geolocate

This implements the same interface as the `Google Maps Geolocation
API <https://developers.google.com/maps/documentation/business/geolocation/>`_
endpoint.

You can point your Firefox Desktop browser at this service by changing the
`geo.wifi.uri` setting in `about:config` to::

    https://location.services.mozilla.com/v1/geolocate

Our service doesn't require a Google API key. At this stage you won't get
any `dailyLimitExceeded`, `keyInvalid`, or `userRateLimitExceeded` errors.
