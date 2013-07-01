Installing / Deploying
======================

Run the following commands to download the database and the server:

.. code-block:: bash

   git clone https://github.com/mozilla/ichnaea
   cd ichnaea
   make

And run the server:

.. code-block:: bash

   bin/circusd circus.ini

This command will launch 2 Python workers.
From there you can access the service on port 7001.

You can also run the service as a daemon:

.. code-block:: bash

   bin/circusd --daemon circus.ini

And interact with it using circusctl. Have a look at `the Circus documentation
<https://circus.readthedocs.org/>`_ for more information on this.
