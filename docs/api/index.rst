=================================
The Mozilla Location Services API
=================================

Overview
========

The Mozilla location services (MLS) API accepts data submission for
geolocation stumbling as well as reporting a location based on
IP addresses, cell or WiFi networks.

API Access Keys
===============

You must identify your client to the service using an API key when
using the search or geolocate APIs. For data submission, we do not
enforce the use of a valid key. We currently do not define a way to
register a new API key.

Each method that the MLS exposes expects the API key to be provided as
a key parameter in the request URI in the form::

    key=<API_KEY>

.. include:: invalid_apikey.rst

.. include:: search_api.rst

.. include:: submit_api.rst

.. include:: geolocate_api.rst
