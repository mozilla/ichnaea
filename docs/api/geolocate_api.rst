.. _api_geolocate:

Geolocate
=========

Purpose
    Determine the current location based on provided data about nearby
    cell or WiFi networks.

Geolocate requests are submitted using a POST request to the URL::

    https://location.services.mozilla.com/v1/geolocate?key=<API_KEY>


Geolocate results
-----------------

This implements the same interface as the `Google Maps Geolocation
API <https://developers.google.com/maps/documentation/business/geolocation/>`_
endpoint. Our service implements all of the standard API.

A successful result will be:

.. code-block:: javascript

    {
        "location": {
            "lat": 51.0,
            "lng": -0.1
        },
        "accuracy": 1200.4
    }
