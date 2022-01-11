===================
Python Requirements
===================

``requirements.in`` files contain the first-order requirements. It is split
into requirements required for production, and those used in development. If
you want to change requirements, change this file.

``requirements.txt`` includes the exact versions and package hashes for the
first-order requirements as well as the requirements-of-requirements. This is
the file used with ``pip install`` to install packages in the Docker image.
``pip-compile``, from pip-tools_, generates and maintains this file using
``requirements.in``.

``requirements-docs.txt`` has the requirements used on ReadTheDocs_ to build
the `Ichnaea documentation`_ on each merge to main. Since this is a
non-production environment, we neither pin nor hash the requirements.

.. _pip-tools: https://github.com/jazzband/pip-tools/
.. _ReadTheDocs: https://readthedocs.org
.. _Ichnaea documentation: https://ichnaea.readthedocs.io/en/latest/

Compiling requirements.txt
==========================

After making changes, the ``.in`` files can be compiled to ``.txt`` output
files by running:

.. code-block:: shell

    make update-reqs

This will start a Docker container and run ``pip-compile`` with the proper
options. Running in the container ensures that the correct dependencies are
chosen for the Docker environment, rather than your host environment.

There will be a warnings at the end of the process:

    The generated requirements file may be rejected by pip install. See # WARNING lines for details.

This is expected. ``pip`` and ``setuptools`` are provided by the container, and
should not be pinned.

To apply the new requirements, rebuild your Docker image:

.. code-block:: shell

    make build

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

Manually upgrading requirements.txt
===================================

To upgrade all the requirements, run ``make shell`` to enter the Docker
environment, and run

.. code-block:: shell

    CUSTOM_COMPILE_COMMAND="make update-reqs" pip-compile --generate-hashes --upgrade

To upgrade a single package, run this instead:

.. code-block:: shell

    CUSTOM_COMPILE_COMMAND="make update-reqs" pip-compile --generate-hashes --upgrade-package <package-name>

You'll need to exit the Docker environment and run ``make build`` to recreate
the Docker image with your changes.

Other tools
===========

pipdeptree_ displays the requirements tree, which can be useful to determine
which package required an unknown package.

.. _pipdeptree: https://github.com/naiquevin/pipdeptree
