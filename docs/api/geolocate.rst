.. _api_geolocate:
.. _api_geolocate_latest:

Geolocate
=========

Purpose
    Determine the current location based on data provided about nearby
    cell or WiFi networks.


Request
-------

Geolocate requests are submitted using a POST request to the URL::

    https://location.services.mozilla.com/v1/geolocate?key=<API_KEY>

This implements the same interface as the `Google Maps Geolocation
API <https://developers.google.com/maps/documentation/business/geolocation/>`_
endpoint. Our service implements all of the standard API.


Response
--------

A successful response will be:

.. code-block:: javascript

    {
        "location": {
            "lat": 51.0,
            "lng": -0.1
        },
        "accuracy": 1200.4
    }
