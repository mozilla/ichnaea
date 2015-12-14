.. _development:

===========
Development
===========

Requirements
------------

In order to install a development version of the service, you need to
have a Linux or Mac OS X machine and
`install docker <https://docs.docker.com/installation/>`_.

On Mac OS X you can use Homebrew to install docker:

.. code-block:: bash

    brew install caskroom/cask/brew-cask
    brew cask install virtualbox
    brew install docker
    brew install docker-machine
    brew install docker-compose

Then you need to create a docker machine:

.. code-block:: bash

    docker-machine create --driver virtualbox --virtualbox-memory 2048 \
        --virtualbox-cpu-count -1 default

You can check it is running via ``docker-machine ls`` and start it via
``docker-machine start default``.

Next configure your shell, so the docker command knows how to connect
to the docker daemon:

.. code-block:: bash

    eval "$(docker-machine env default)"

You also need to add an entry into your ``/etc/hosts`` file. On Mac OS X
you need to specify the IP of the running docker machine, on Linux use
`127.0.0.1`:

.. code-block:: bash

    docker-machine ip default

Put the value into the hosts file, for example:

.. code-block:: ini

    192.168.99.100  ichnaea.dev


Code
----

Now run the following command to get the code:

.. code-block:: bash

    git clone https://github.com/mozilla/ichnaea
    cd ichnaea

In order to run the code you need to have Python 2.6, 2.7 or 3.4 installed
on your system. The default Makefile also assumes a `virtualenv-2.6`
command is globally available. If this isn't true for your system,
please create a virtualenv manually inside the ichnaea folder before
continuing (``/path/to/virtualenv .``).

The first time you need to download some shared docker images. You can
manually trigger this by calling:

.. code-block:: bash

    docker-compose up -d

Then run make:

.. code-block:: bash

    make

Now you can run the web app on for example port 7001:

.. code-block:: bash

    ICHNAEA_CFG=location.ini bin/gunicorn -b 127.0.0.1:7001 \
        -c python:ichnaea.webapp.settings ichnaea.webapp.app:wsgi_app

The celery processes are started via:

.. code-block:: bash

    ICHNAEA_CFG=location.ini bin/celery -A ichnaea.async.app:celery_app beat

    ICHNAEA_CFG=location.ini bin/celery -A ichnaea.async.app:celery_app worker \
        -Ofair --no-execv --without-mingle --without-gossip


Documentation
-------------

In order to create and test the documentation locally run:

.. code-block:: bash

    make docs

The documentation will be available in ``docs/build/html/index.html``.


Python Dependencies
-------------------

The project uses `requires.io <https://requires.io/github/mozilla/ichnaea/requirements/?branch=master>`_ 
to track whether or not the Python dependencies are outdated.

If they are, update the version pins in the various `requirements/*.txt`
files and rerun `make`, `make docs` or `make test`, depending on which
requirements have changed.


CSS / JS / Images
-----------------

The project depends on a number of external web assets. Those dependencies
are tracked via npm and bower.

In order to install them, run:

.. code-block:: bash

    make css
    make js

This will install a couple of build tools under `node_modules` and various
assets under `bower_components`. It will also copy, compile and minify
files into various folders under `ichnaea/content/static/`.

To check if the external assets are outdated run:

.. code-block:: bash

    ./node_modules/.bin/bower list

To force-update the build tools run:

.. code-block:: bash

    make node_modules -B


Cleanup
-------

In case the local environment gets into a weird or broken state, it can
be cleaned up by running:

.. code-block:: bash

    make clean

Of course one can also delete the entire git repository and start from
a fresh checkout.


Release Build
-------------

The default `make` / `make build` target installs a local development
version including database setup and testing tools. For a production
environment or release pipeline one can instead use:

.. code-block:: bash

    make release

This will not do any database setup and only install production
dependencies. It will also create a virtualenv and install the ichnaea
code itself via `bin/python setup.py install`, so that a copy will be
installed into `lib/pythonX.Y/site-packages/`.

The step will also compile all py files to pyc files and remove any files
from the tree which aren't compatible with the active Python version
(blocklist in the `compile.py` script). The removal step ensures that
any build tools (for example rpmbuild / mock) that typically call
`compileall.compile_dir` will work, without breaking on the incompatible
files.
