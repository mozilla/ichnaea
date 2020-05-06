"""
Holds global web application state and the WSGI handler.

You can run this script for a one-process webapp.

Further, you can pass in ``--check`` which will create the app and then exit
making it easier to suss out startup and configuration issues.

"""

import sys

from waitress import serve

from ichnaea.conf import settings
from ichnaea.webapp.config import main, shutdown_worker


# Internal module global holding the runtime web app.
_APP = None


def wsgi_app(environ, start_response):
    """
    Actual WSGI application endpoint, used on the command line via:

    .. code-block:: bash

        bin/gunicorn -c python:ichnaea.webapp.gunicorn_settings \
            ichnaea.webapp.app:wsgi_app

    At startup reads the app config and calls
    :func:`ichnaea.webapp.config.main` once to setup the web app stored
    in the :data:`ichnaea.webapp.app._APP` global.
    """
    global _APP

    if _APP is None:
        _APP = main(ping_connections=True)
        if environ is None and start_response is None:
            # Called as part of gunicorn's post_worker_init
            return _APP

    return _APP(environ, start_response)


def worker_exit(server, worker):
    shutdown_worker(_APP)


if __name__ == "__main__":
    if "--check" in sys.argv:
        main(ping_connections=False)
    else:
        serve(
            main(ping_connections=True),
            host="0.0.0.0",
            port=8000,
            expose_tracebacks=settings("local_dev_env"),
        )
