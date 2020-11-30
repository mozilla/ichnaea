===================
Python Requirements
===================

Ichnaea uses ``pip-compile`` from pip-tools_ to help manage Python
requirements.

.. _pip-tools: https://github.com/jazzband/pip-tools/

Input files
===========

The ``*.in`` files contain the versions of the first-order requirements, and
are split by purpose. If you want to update requirements, update these files.

The input files are:

* ``shared.in`` - Requirements used by both documentation and production.
* ``docs.in`` - The requirements needed to build documentation.
* ``prod.in`` - The requirements needed to run the service in production.
* ``dev.in`` - The requirements needed to run the development environment.
  This includes both the documentation and production requirements, and are
  installed in the Docker image.

Output files
============

The output files are the ones used with ``pip install`` to install
requirements, and have the same root names as the input files (``shared.txt``
is generated from ``shared.in``).

The important ones are:

* ``docs.txt`` - Used on ReadTheDocs_ to build the `Ichnaea documentation`_ on
  each merge to main.
* ``dev.txt`` - Used to install all the Python packages inside the Docker
  image.

The two other files, ``shared.txt`` and ``prod.txt``, are not installed
directly, but are used in the ``pip-compile`` process.

.. _ReadTheDocs: https://readthedocs.org
.. _Ichnaea documentation: https://ichnaea.readthedocs.io/en/latest/

Compiling output files from input
=================================

After making changes, the ``.in`` files can be compiled to ``.txt`` output
files by running:

.. code-block:: shell

    make update-reqs

This will start a Docker container and run ``pip-compile`` with the proper
options. Running in the container ensures that the correct dependencies are
chosen for the Docker environment, rather than your host environment.

There will be warnings printed as the files are compiled:

    The generated requirements file may be rejected by pip install. See # WARNING lines for details.

This is expected. ``pip`` and ``setuptools`` are provided by the container, and
should not be pinned.

Automated Updates
=================

Dependabot_ opens PRs for updates around the first of the month.
It also opens PRs for security updates when they are available.
It seems to have some support for ``pip-tools``, but it may be
necessary to manually run ``make update-reqs`` to
correctly regenerate the requirements.

paul-mclendahand_ is useful for packaging several PRs into a single PR, and
avoiding the rebase / rebuild / test cycle when merging one Dependabot PR at a
time.

.. _Dependabot: https://dependabot.com
.. _paul-mclendahand: https://github.com/willkg/paul-mclendahand

Other tools
===========

pipdeptree_ displays the requirements tree, which can be useful to determine
which package required an unknown package.

hashin_ is useful for generating a list of hashes. We used it exclusively
before ``pip-compile``, and it may be handy if you need to manually update a
``.txt`` file.

.. _pipdeptree: https://github.com/naiquevin/pipdeptree
.. _hashin: https://github.com/peterbe/hashin
