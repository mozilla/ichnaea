# Requirements

Ichnaea uses `pip-compile` from [pip-tools](https://github.com/jazzband/pip-tools/)
to help manage requirements.

## Input files

The ``*.in`` files contain the versions of the first-order requirements, and
are split by purpose. If you want to update requirements, update these files.

The input files are:

* ``shared.in`` - Requirements used by both documentation and production.
* ``docs.in`` - The requirements needed to build documentation.
* ``prod.in`` - The requirements needed to run the service in production.
* ``dev.in`` - The requirements needed to run the development environment.
  This includes both the documentation and production requirements.

## Output files

The output files are the ones used with ``pip install`` to install
requirements, and have the same root names as the input files (``shared.txt``
is generated from ``shared.in``).

The important ones are:

* ``docs.txt`` - Used on [ReadTheDocs](https://readthedocs.org) to build the
  [Ichnaea documentation](https://ichnaea.readthedocs.io/en/latest/) on each
  merge to main.
* ``dev.txt`` - Used to install all the Python packages inside the Docker
  image.

The two other files ``shared.txt`` and ``prod.txt`` are not installed directly,
but are used in the ``pip-compile`` process.

## Compiling output files from input

After making changes, the ``.in`` files can be compiled to ``.txt`` output
files by running:

    make reqs-regen

This will start a Docker container and run ``pip-compile`` with the proper
options. Running in the container ensures that the correct dependencies are
chosen for the Docker environment, rather than your host environment.

There will be warnings printed as the files are compiled:

    The generated requirements file may be rejected by pip install. See # WARNING lines for details.

This is expected. ``pip`` and ``setuptools`` are provided by the container,
and should not be pinned.

A similar command will check that there are no changes in the output files:

    make reqs-verify

## Other tools

Other tools are used in the requirements process.

[Dependabot](https://dependabot.com) opens PRs for security updates when
available, and for other updates around the first of the month.
[paul-mclendahand](https://github.com/willkg/paul-mclendahand) is useful for
packaging several PRs into a single PR, and avoiding the rebase / rebuild /
test cycle when merging one Dependabot PR at a time

[pipdeptree](https://github.com/naiquevin/pipdeptree) displays the
requirements tree, which can be useful to determine which package required
an unknown package.

[hashin](https://github.com/peterbe/hashin) is useful for generating a list
of hashes. We used it exclusively before `pip-compile`, and it may be handy
if you need to manually update a `.txt` file.
