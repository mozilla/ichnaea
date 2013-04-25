===============
Mozilla Ichnaea
===============

**Mozilla Ichnaea** is a service to provide geo location coordinates in
response to user requests.

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

   changelog


Development
===========

All source code is available on `github under ichnaea
<https://github.com/mozilla/ichnaea>`_.

Bugs and support issues should be reported on the `ichnaea github issue tracker
<https://github.com/mozilla/ichnaea/issues>`_.

The developers of ``ichnaea`` can frequently be found on the Mozilla IRC
network in the #geo channel.


How to run your own server
==========================

Run the following commands to download the database and the server:

.. code-block:: bash

   git clone https://github.com/mozilla/ichnaea
   cd ichnaea
   make
   curl http://opencellid.enaikoon.de:8080/gpsSuiteCellIDServer/exportFiles/basestations.tar.gz | tar xzC data/
   bin/ichnaea_import ichnaea.ini data/basestations.csv


Then run the server:

.. code-block:: bash

   bin/pserve ichnaea.ini


From there you can access the service on port 7001.


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
