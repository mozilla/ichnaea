======================
Installing / Deploying
======================

MySQL / RDS
===========

The application is written and tested against MySQL 5.6.x or Amazon RDS of the
same version. The default configuration works for the most part. There are
just three changes you need to do. For example via the my.cnf:

.. code-block:: ini

    [mysqld]
    innodb_file_format=Barracuda
    innodb_strict_mode=on
    sql-mode="STRICT_TRANS_TABLES"


Heka configuration
==================

The default configuration in ichnaea.ini assumes that you are running
a hekad instance listening on for UDP messages on port 5565.  This is
a pretty standard heka configuration, so if you have any problems, you
should consult the heka documentation to verify that messages are
being captured properly by hekad.

To get heka to log exceptions to Sentry, you will need to obtain the
DSN for your Sentry instance.  Edit ichnaea.ini in the
`heka_plugin_raven` section with your actual DSN and exceptions should
start appearing in Sentry.

Code
====

Run the following commands to download the database and the server:

.. code-block:: bash

   git clone https://github.com/mozilla/ichnaea
   cd ichnaea
   make

And run the server:

.. code-block:: bash

   bin/circusd circus.ini

This command will launch 2 web server processes, one celery beat daemon and
two celery worker processes. You can access the web service on port 7001.

You can also run the service as a daemon:

.. code-block:: bash

   bin/circusd --daemon circus.ini

And interact with it using circusctl. Have a look at `the Circus documentation
<https://circus.readthedocs.org/>`_ for more information on this.
