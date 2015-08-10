=======
Ichnaea
=======

``Ichnaea`` is a service to provide geolocation coordinates
from other sources of data (cell or WiFi networks, GeoIP, etc.).
It is using both :term:`Cell-ID` and Wi-Fi based positioning (:term:`WPS`)
approaches.

Mozilla hosts an instance of this service, called the `Mozilla Location
Service <https://wiki.mozilla.org/CloudServices/Location>`_
(:term:`MLS`).

You can interact with the service in two ways:

- If you know where you are, submit information about the radio environment
  to the service to increase its quality.

- or locate yourself, based on the radio environment around you.


About the name
==============

In Greek mythology, Ichnaea (Iknaia) means "the tracker".


Table of contents
=================

.. toctree::
   :maxdepth: 2

   usage
   api/index
   import_export
   deploy
   config
   development
   testing
   calculation
   metrics
   internal_api/index
   glossary
   changelog


Development
===========

All source code is available on `github under ichnaea
<https://github.com/mozilla/ichnaea>`_.

The developers of ``ichnaea`` can frequently be found on the `Mozilla IRC
network <https://wiki.mozilla.org/IRC>`_ in the #geo channel.


Development CI Status
=====================

.. image:: https://travis-ci.org/mozilla/ichnaea.svg?branch=master
    :alt: Travis CI build report
    :target: https://travis-ci.org/mozilla/ichnaea


License
=======

The ``ichnaea`` source code is offered under the Apache License 2.0.
