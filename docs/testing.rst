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

Or run individual test modules or functions via for example:

.. code-block:: bash

    make test TESTS=ichnaea.tests.test_geoip:TestDatabase.test_open


Testing Tasks
-------------

The project includes a good number of asynchronous tasks, executed by celery
in the code. The easiest way to test them is by writing unit tests and calling
the task functions directly.

In order to do more integration testing, you can also manually queue a task
by using the celery `call` command. For example:

.. code-block:: bash

    ICHNAEA_CFG=location.ini bin/celery -A ichnaea.async.app:celery_app call \
    ichnaea.data.tasks.update_cell --args='[1000, ]’

You then need to run the celery worker process and it will pick up the task
from the queue and execute it:

.. code-block:: bash

    ICHNAEA_CFG=location.ini bin/celery \
    -A ichnaea.async.app:celery_app worker -c 1


Testing Multiple Python Versions
--------------------------------

The project supports multiple Python versions. In order to run the tests
against all of them locally, we are using tox:

.. code-block:: bash

    bin/tox

You can explicitly state what Python versions to test:

.. code-block:: bash

    bin/tox -e=py{26,27,34}

You can also run a subset of all tests, the same way as via `make test`:

.. code-block:: bash

    bin/tox TESTS=ichnaea.tests.test_util

If the tox environment got into a weird state, just recreate it:

.. code-block:: bash

    bin/tox --recreate

Of course these options can be combined, for example:

.. code-block:: bash

    bin/tox -e=py{34} TESTS=ichnaea.tests.test_util

Since the project relies on a number of non-Python dependencies, each
tox environment is created from a full copy of the git repo. The ease
testing the `ichnaea` code package is then removed from inside each
tox environment and finally `bin/install -e ichnaea /path/to/parent/repo`
called. This means the code inside the top-level `ichnaea` code package
is actually used from inside each tox environment.

If you set a pdb breakpoint in the normal main code, you'll thus get
an easy way to have a pdb inside each tox environment.
