===============
Mozilla Ichnaea
===============

**Mozilla Ichnaea** is a service to provide geo location coordinates in
response to user requests.

More information about the specific instance hosted by Mozilla can be found
at https://wiki.mozilla.org/Services/Location

We currently provide two API:

- one for searching for your current location, given what you
  see around you.

- one for submitting information about what you see around you,
  given a location.


API
===

.. services::
   :modules: ichnaea.views
   :service: search


.. services::
   :modules: ichnaea.views
   :service: submit


Table of contents
=================

.. toctree::
   :maxdepth: 2

   deploy
   changelog


Development
===========

All source code is available on `github under ichnaea
<https://github.com/mozilla/ichnaea>`_.

Bugs should be reported in the `Mozilla Services :: Location component of
Bugzilla <https://bugzilla.mozilla.org/describecomponents.cgi?product=Mozilla%20Services&component=Location>`_.

The developers of ``ichnaea`` can frequently be found on the Mozilla IRC
network in the #geo channel.



Extra data sources
==================

**www.opencellids.org/en/download/**

- http://opencellid.enaikoon.de:8080/gpsSuiteCellIDServer/exportFiles/basestations.tar.gz
- http://opencellid.enaikoon.de:8080/gpsSuiteCellIDServer/exportFiles/measurements.tar.gz

**dump.opencellid.org**

- http://dump.opencellid.org/cells.txt.gz
- http://dump.opencellid.org/measures.txt.gz


License
=======

The ``mozilla-ichnaea`` source code is offered under the Apache License 2.0.

The initial data is taken from `opencellid.org <http://opencellid.org/>`_
kindly offered under the `Creative Common Attribution-Share Alike 3.0 Unported
<http://creativecommons.org/licenses/by-sa/3.0/>`_ license. In addition data
is taken from the opencellid server hosted by
`enaikoon.de <http://www.enaikoon.de>`_ under the same license.
