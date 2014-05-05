===============
Mozilla Ichnaea
===============

``Mozilla Ichnaea`` is an application to provide geo-location coordinates
from other sources of data (cell, wifi networks, IP addresses, etc.).

More information about the specific instance hosted by Mozilla can be found
at https://wiki.mozilla.org/CloudServices/Location

We currently provide three API endpoints:

- one for submitting information about what you see around you,
  given a location.

- one for searching for your current location, given what you
  see around you.

- another one for searching for your current location, compatible
  with Google's geolocation API.


About the name
==============

In Greek mythology, Ichnaea (Iknaia) means "the tracker".


Table of contents
=================

.. toctree::
   :maxdepth: 2

   api/index.rst
   cell
   calculation
   deploy
   changelog


Development
===========

All source code is available on `github under ichnaea
<https://github.com/mozilla/ichnaea>`_.

The developers of ``ichnaea`` can frequently be found on the `Mozilla IRC
network <https://wiki.mozilla.org/IRC>`_ in the #geo channel.


License
=======

The ``mozilla-ichnaea`` source code is offered under the Apache License 2.0.
