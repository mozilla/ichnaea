.. _usage:

=================
Using the service
=================

You can either use the service directly via the HTTP service APIs.
Or you can use one of the existing clients or integrations.


HTTP API
--------

You can use the :ref:`service_api` directly via a command line client
like curl or via any programming language allowing you to do HTTP calls.


Apps
----

A number of apps with different capabilities exist that allow you to use
or contribute to the service. Please have a look at the
`Apps listing <https://location.services.mozilla.com/apps>`_ on the service
website to learn more.


Firefox Desktop
---------------

You can point your Firefox Desktop browser version 24 or later at this service
by changing the `geo.wifi.uri` setting in `about:config`.
If you want to use the Mozilla hosted service, the exact settings is::

    https://location.services.mozilla.com/v1/geolocate?key=<API_KEY>

If you are using an official Mozilla build of Firefox you can use
`%GOOGLE_API_KEY%` (including the percent signs) as the API key for the
Mozilla hosted service. The official Mozilla Google keys are whitelisted
to also work for the Mozilla location service.

This only works if your version of Firefox already uses the new Google
Geolocation API. If you reset the settings value it should have been::

    https://www.googleapis.com/geolocation/v1/geolocate?key=%GOOGLE_API_KEY%

If you see a different value, please update to Firefox 24 or later.
