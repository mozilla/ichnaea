.. _api_region:
.. _api_region_latest:

Region
======

Purpose
    Determine the current region based on data provided about nearby
    cell or WiFi networks and based on the IP address used to access
    the service.

The responses use region codes and names from the
`GENC dataset <http://www.gwg.nga.mil/ccwg.php>`_, which is for the
most part compatible with the ISO 3166 standard. While the API
endpoint and JSON payload refers to `country`, no claim about the
political status of any region is made by this service.

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
