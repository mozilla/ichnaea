.. _api_region:
.. _api_region_latest:

===================
Region: /v1/country
===================

**Purpose:** Determine the current region based on data provided about nearby
Bluetooth, cell, or WiFi networks the IP address used to access the service.

The responses use region codes and names from the `GENC dataset
<https://nsgreg.nga.mil/genc/discovery>`_, which is mostly compatible with the ISO
3166 standard.

.. Note::

   While the API endpoint and JSON payload refers to `country`, no claim about
   the political status of any region is made by this service.

.. contents::
   :local:

Request
=======

Requests are submitted using an HTTP POST request to the URL::

    https://location.services.mozilla.com/v1/country?key=<API_KEY>

This implements the same interface as the :ref:`api_geolocate` API.

The simplest request contains no extra information and simply relies
on the IP address to provide a response.


Response
========

Here's an example successful response:

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
