"""
Holds global web application state and the WSGI handler.
"""

from ichnaea.webapp.config import (
    main,
    shutdown_worker,
)

# Internal module global holding the runtime web app.
_APP = None


def wsgi_app(environ, start_response):  # pragma: no cover
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


def worker_exit(server, worker):  # pragma: no cover
    shutdown_worker(_APP)
