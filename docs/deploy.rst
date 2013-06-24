Installing / Deploying
======================

Run the following commands to download the database and the server:

.. code-block:: bash

   git clone https://github.com/mozilla/ichnaea
   cd ichnaea
   make
   curl http://opencellid.enaikoon.de:8080/gpsSuiteCellIDServer/exportFiles/basestations.tar.gz | tar xzC data/
   bin/ichnaea_import ichnaea.ini data/basestations.csv

Make sure Redis is running. Under Debuntu:

.. code-block:: bash

   sudo apt-get install redis-server
   sudo service redis start

Then run the server:

.. code-block:: bash

   bin/circusd circus.ini

This command will launch 2 python workers and a redis worker.
From there you can access the service on port 7001.

You can also run the service as a daemon:

.. code-block:: bash

   bin/circusd --daemon circus.ini

And interact with it using circusctl. Have a look at `the Circus documentation
<https://circus.readthedocs.org/>`_ for more information on this.
