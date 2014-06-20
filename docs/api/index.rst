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
using any of the APIs. We currently do not define a way to register
a new API key. Please contact us via our public mailing list or IRC
channel if you want to use MLS in your own application.

Each method that the MLS exposes expects the API key to be provided as
a key parameter in the request URI in the form::

    key=<API_KEY>

.. include:: invalid_apikey.rst

.. include:: search_api.rst

.. include:: submit_api.rst

.. include:: geolocate_api.rst

.. include:: geosubmit_api.rst
