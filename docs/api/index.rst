.. _service_api:

============
Services API
============

The service APIs accept data submission for geolocation stumbling as well as
reporting a location based on IP addresses, cell, or WiFi networks.

New client developments should use the :ref:`api_region_latest`,
:ref:`api_geolocate_latest`, or :ref:`api_geosubmit_latest` APIs.

Requesting an API Key
=====================

The api key has a set daily usage limit of about 100,000 requests. As we aren't
offering a commercial service, please note that we do not make any guarantees
about the accuracy of the results or the availability of the service.

Please make sure that you actually need the raw API access to
perform geolocation lookups. If you just need to get location data
from your web application, you can directly use the
`HTML5 API <https://developer.mozilla.org/en-US/docs/Web/API/Geolocation_API>`_.

To apply for an API key, please
`fill out this form
<https://docs.google.com/forms/d/e/1FAIpQLSf2JaJm8V1l8TS_OiyjodkpYsagOhM1LNo_SmPDDAVKdmQg8A/viewform>`_.
When filling out the form, please make sure to describe your use-case and
intended use of the service. Our
`Developer Terms of Service
<https://location.services.mozilla.com/terms>`_ govern the use of MLS API keys.

We'll try to get back to you within a few days, but depending on vacation times
it might take longer.

API Access Keys
===============

.. Note::

   Mozilla is currently evaluating its MLS service and terms and is not
   currently distributing API keys.

You can anonymously submit data to the service without an API key via
any of the submission APIs.

You must identify your client to the service using an API key when
using one of the :ref:`api_region_latest` or :ref:`api_geolocate_latest` APIs.

If you want or need to specify an API key, you need to be provide
it as a query argument in the request URI in the form::

    https://location.services.mozilla.com/<API>?key=<API_KEY>

Each API key can be rate limited per calendar day, but the default is to allow
an unlimited number of requests per day.


Errors
======

Each of the supported APIs can return specific error responses. In addition
there are some general error responses.


Invalid API Key
---------------

If an API key was required but either no key was provided or the provided key
was invalid, the service responds with a ``keyInvalid`` message and HTTP 400
error code:

.. code-block:: javascript

    {
        "error": {
            "errors": [{
                "domain": "usageLimits",
                "reason": "keyInvalid",
                "message": "Missing or invalid API key."
            }],
            "code": 400,
            "message": "Invalid API key"
        }
    }


API Key Limit
-------------

API keys can be rate limited. If the limit for a specific API key is exceeded,
the service responds with a ``dailyLimitExceeded`` message and a HTTP 403
error code:

.. code-block:: javascript

    {
        "error": {
            "errors": [{
                "domain": "usageLimits",
                "reason": "dailyLimitExceeded",
                "message": "You have exceeded your daily limit."
            }],
            "code": 403,
            "message": "You have exceeded your daily limit."
        }
    }


Parse Error
-----------

If the client sends a malformed request, typically sending malformed or invalid
JSON, the service will respond with a ``parseError`` message and a HTTP 400
error code:

.. code-block:: javascript

    {
        "error": {
            "errors": [{
                "domain": "global",
                "reason": "parseError",
                "message": "Parse Error"
            }],
            "code": 400,
            "message": "Parse Error"
            "details": {
                "decode": "JSONDecodeError('Expecting value: line 1 column 1 (char 0)')"
            }
        }
    }

The ``details`` item will be a mapping with the key ``"decode"`` or
``"validation"``.  If the key is ``"decode"``, the value will be a string
describing a fundamental decoding issue, such as failing to decompress gzip
content, to convert to unicode from the declared charset, or to parse as JSON.
If the key is ``"validation"``, the value will describe validation errors in
the JSON payload.


Service Error
-------------

If there is a transient service side problem, the service might respond with
HTTP 5xx error codes with unspecified HTTP bodies.

This might happen if part of the service is down or unreachable. If you
encounter any 5xx responses, you should retry the request at a later time. As a
service side problem is unlikely to be resolved immediately, you should wait a
couple of minutes before retrying the request for the first time and a couple
of hours later if there's still a problem.


APIs
====

.. toctree::
   :maxdepth: 1

   geolocate
   region
   geosubmit2
   geosubmit
   submit


History
=======

The service launched in 2013, and first offered custom ``/v1/search/`` and
:ref:`/v1/submit/ <api_submit>` APIs, used by the MozStumbler_ app. Later that
year the :ref:`/v1/geolocate <api_geolocate>` API was implemented, to reduce
the burden on clients that already used the
`Google Maps Geolocation API`_.  This was followed by the
:ref:`/v1/geosubmit <api_geosubmit>` API, to make contribution more consistant.

In 2014, the ``/v1/geosubmit`` and ``/v1/geolocate`` API were recommended for
client development, and the ``/v1/submit`` and ``/v1/search`` APIs were marked
as deprecated.

In 2015, the :ref:`/v2/geosubmit <api_geosubmit>` API was added, to expand the
submitted data fields and accept data from partners. The
:ref:`/v1/country <api_region>` API was also added, to provide region rather
than position lookups.

In 2016, a ``/v1/transfer`` API was added, for bulk transfers of data from one
instance of Ichnaea to another. This was also when work started on the 2.0
implementation of Ichnaea, and `MozStumbler switched`_ to ``/v1/geolocate`` and
``/v1/geosubmit``.

In 2017, the ``/v1/transfer`` API was removed from the 2.0 branch, and Mozilla
stopped active development of Ichnaea, leaving 1.5 as the production
deployment.

In 2019, Ichnaea development started up again, to prepare the 2.0 codebase
for production. The deprecated ``/v1/search`` API was removed.

.. _MozStumbler: https://github.com/mozilla/MozStumbler
.. _`Google Maps Geolocation API`: https://developers.google.com/maps/documentation/geolocation/intro
.. _`MozStumbler switched`: https://github.com/mozilla/MozStumbler/pull/1500
