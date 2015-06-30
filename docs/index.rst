=======
Ichnaea
=======

``Ichnaea`` is a service to provide geolocation coordinates
from other sources of data (cell or WiFi networks, GeoIP, etc.).

Mozilla hosts an instance of this service, called the `Mozilla Location
Service or MLS <https://wiki.mozilla.org/CloudServices/Location>`_.


You can interact with the service in two ways:

- If you know where you are, submit information about the radio environment
  to the service

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
   calculation
   import_export
   deploy
   development
   testing
   metrics
   internal_api/index
   changelog


Development
===========

All source code is available on `github under ichnaea
<https://github.com/mozilla/ichnaea>`_.

The developers of ``ichnaea`` can frequently be found on the `Mozilla IRC
network <https://wiki.mozilla.org/IRC>`_ in the #geo channel.


License
=======

The ``ichnaea`` source code is offered under the Apache License 2.0.
