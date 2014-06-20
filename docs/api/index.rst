.. _service_api:

============
Services API
============

Overview
========

The service APIs accept data submission for geolocation stumbling as
well as reporting a location based on IP addresses, cell or WiFi networks.

Historically the service first offered the custom :ref:`api_search` and
:ref:`api_submit` APIs. Later it was decided to also implement the
:ref:`api_geolocate` API to lessen the burden on clients that want to
support multiple location services. As an extension to this the
:ref:`api_geosubmit` was added to offer a consistent way to contribute
back data to the service.

New client developments should use the :ref:`api_geolocate` and
:ref:`api_geosubmit` APIs. At some point in the future the
:ref:`api_search` and :ref:`api_submit` APIs will be deprecated and retired.


API Access Keys
===============

You must identify your client to the service using an API key when
using any of the APIs. We currently do not define a way to register
a new API key. Please contact us via our public mailing list or IRC
channel if you want to use this service in your own application.

Each method that the service exposes expects the API key to be provided
as a key parameter in the request URI in the form::

    key=<API_KEY>

.. include:: invalid_apikey.rst

.. include:: geolocate_api.rst

.. include:: geosubmit_api.rst

.. include:: search_api.rst

.. include:: submit_api.rst
