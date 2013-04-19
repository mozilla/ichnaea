===============
Mozilla Ichnaea
===============

**Mozilla Ichnaea** is a service to provide geo location coordinates in
response to user requests.

We currently provide two API:

- one for searching for your current location, given what you
  see around you.

- one for sending back information about what you see around you,
  given a location


API
===

.. services::
   :modules: ichnaea.views
   :service: location_search


.. services::
   :modules: ichnaea.views
   :service: location_measurement


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
   curl http://dump.opencellid.org/cells.txt.gz | gunzip > data/cells.txt
   bin/ichnaea_import ichnaea.ini data/cells.txt


Then run the server:

.. code-block:: bash

   bin/pserve ichnaea.ini


From there you can access the service on port 7001.
