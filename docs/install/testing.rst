.. _testing:

=======
Testing
=======

.. note:: Since the tests use a real database and Redis connection,
          you cannot parallelize any tests.

Unit Tests
----------

If you have a local development environment, you can run all tests
including coverage tests via:

.. code-block:: bash

    ./server test

Or run individual test modules via for example:

.. code-block:: bash

    ./server test TESTS=ichnaea.tests.test_geoip
