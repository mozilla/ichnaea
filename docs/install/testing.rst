.. _testing:

=======
Testing
=======

.. note:: Since the tests use a real database and Redis connection,
          you cannot parallelize any tests.

Unit Tests
----------

If you have a local development environment setup, you can run all tests
including coverage tests via:

.. code-block:: bash

    make test

Or run individual test modules via for example:

.. code-block:: bash

    make test TESTS=ichnaea.tests.test_geoip


Testing Tasks
-------------

The project includes a good number of asynchronous tasks, executed by Celery
in the code. The easiest way to test them is by writing unit tests and calling
the task functions directly.

In order to do more integration testing, you can also manually queue a task
by using the celery `call` command. For example:

.. code-block:: bash

    ICHNAEA_CFG=location.ini bin/celery -A ichnaea.async.app:celery_app call \
        ichnaea.data.tasks.update_cell --args='[1000, ]'

You then need to run the celery worker process and it will pick up the task
from the queue and execute it:

.. code-block:: bash

    ICHNAEA_CFG=location.ini bin/celery \
        -A ichnaea.async.app:celery_app worker -c 1
