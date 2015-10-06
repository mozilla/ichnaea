.. _api_region:
.. _api_region_latest:

Region
======

Purpose
    Determine the current region based on data provided about nearby
    cell or WiFi networks and based on the IP address used to access
    the service.


Request
-------

Requests are submitted using a POST request to the URL::

    https://location.services.mozilla.com/v1/country?key=<API_KEY>

This implements the same interface as the :ref:`api_geolocate` API.

The simplest request contains no extra information and simply relies
on the IP address to provide a response:

.. code-block:: javascript

    {}

Response
--------

A successful response will be:

.. code-block:: javascript

    {
        "country_code": "US",
        "country_name": "United States"
    }

Should the response be based on a GeoIP estimate:

.. code-block:: javascript

    {
        "country_code": "US",
        "country_name": "United States",
        "fallback": "ipf"
    }

If no region could be determined, a HTTP status code 404 will be returned:

.. code-block:: javascript

    {
        "error": {
            "errors": [{
                "domain": "geolocation",
                "reason": "notFound",
                "message": "Not found",
            }],
            "code": 404,
            "message": "Not found",
        }
    }
