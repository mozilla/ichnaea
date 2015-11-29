.. _deploy:

======================
Installing / Deploying
======================

MySQL / Amazon RDS
==================

The application is written and tested against MySQL 5.6.x or Amazon RDS of the
same version. The default configuration works for the most part. There are
just three changes you need to do. For example via the my.cnf:

.. code-block:: ini

    [mysqld]
    innodb_file_format=Barracuda
    innodb_strict_mode=on
    sql-mode="NO_ENGINE_SUBSTITUTION,STRICT_TRANS_TABLES"


Redis / Amazon ElastiCache
==========================

The application uses Redis as a queue for the asynchronous task workers and
also uses it directly as a cache and to track API key rate limitations.

You can install a standard local Redis for development or production use.
The application is also compatible with Amazon ElastiCache (Redis).


Amazon S3
=========

The application uses Amazon S3 for various tasks, including backup of
:term:`observations`, export of the aggregated cell table and hosting of
the data map image tiles.

All of these are triggered by asynchronous jobs and you can disable them
if you are not hosted in an Amazon environment.

If you use Amazon S3 you might want to configure a lifecycle policy to
delete old export files after a couple of days and :term:`observation`
data after one year.


Statsd / Sentry
===============

The application uses Statsd to aggregate stats and Sentry to log
exception messages.

The default configuration in location.ini assumes that you are running
a Statsd instance listening for UDP messages on port 8125.

To get the app to log exceptions to Sentry, you will need to obtain the
DSN for your Sentry instance. Edit location.ini and in the `sentry` section
put your real DSN into the `dsn` setting.

Installation of Statsd and Sentry are outside the scope of this documentation.


Dependencies
============

The code includes functionality to render out image tiles for a data map
of places where observations have been made. This part of the code relies
on two external projects. One is the
`datamaps image tile generator <https://github.com/ericfischer/datamaps>`_
the other is `pngquant <http://pngquant.org/>`_. Make sure to install both
of them and make their binaries available on your system path. The datamaps
package includes the `encode`, `enumerate` and `render` tools and the
pngquant package includes a tool called `pngquant`.
