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
:ref:`api_geosubmit2` was added to offer a consistent way to contribute
back data to the service.

New client developments should use the :ref:`api_geolocate` and
:ref:`api_geosubmit2` APIs. At some point in the future the
:ref:`api_search` and :ref:`api_submit` APIs will be deprecated and retired.


API Access Keys
===============

You must identify your client to the service using an API key when
using any of the search/lookup APIs.

You can use API keys for the submission API's, but are not required
to do so.

Each method that the service expects the API key to be provided
as a (optional) key parameter in the request URI in the form::

    key=<API_KEY>

Each API key can be rate limited per calendar day, but the default is
to allow an unlimited number of requests per day.

.. include:: invalid_apikey.rst

.. include:: geolocate_api.rst

.. include:: geosubmit2_api.rst

.. include:: geosubmit_api.rst

.. include:: country_api.rst

.. include:: search_api.rst

.. include:: submit_api.rst
