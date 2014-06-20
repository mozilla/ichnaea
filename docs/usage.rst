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


MozStumbler for Android
-----------------------

MozStumbler is an open source Android application, which both collects data to
enhance the service and also includes a test mode to show ones location on a
map.

You can find `MozStumbler on github <https://github.com/mozilla/MozStumbler>`_
to download it or to contribute to its development.


Firefox for Android
-------------------

Nightly versions of Firefox for Android include a way to contribute data and
enhance this service. In order to enable this, you need to go to the
Mozilla settings section and look for the contribution option under
data choices.


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


Firefox OS
----------

Integration of this service into Firefox OS is an ongoing process. If the
specific Firefox OS device uses this service depends on a number of factors
including which chipset is used in the device, which manufacturer built
the device and via what partner and channel it was sold or given out.

In general client side code to talk to this service appeared in Firefox OS
version 1.3T and 1.4.


FxStumbler
----------

FxStumbler is an open source Firefox OS application similar in purpose to
MozStumbler. It collects data about the radio environment to enhance the
service.

To contribute to the development of `FxStumbler visit it on github
<https://github.com/clochix/FxStumbler>`_.


Geoclue
-------

Geoclue is a D-Bus service that provides location information. It has
integrated this service as a location provider. You can find out more about
`geoclue on its homepage <http://www.freedesktop.org/wiki/Software/GeoClue/>`_.
