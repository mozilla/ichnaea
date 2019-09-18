"""
Holds global web application state and the WSGI handler.
"""

import logging

from waitress import serve

from ichnaea.webapp.config import main, shutdown_worker


LOGGER = logging.getLogger("ichnaea")


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


def log_access_factory(wsgi_app):
    """WSGI middleware for logging HTTP requests."""

    def handle(environ, start_response):
        method = environ["REQUEST_METHOD"]
        path = environ.get("PATH_INFO", "")

        def log_response(status, headers, exc_info=None):
            content_length = ""
            for key, val in headers:
                if key.lower() == "content-length":
                    content_length = "(%s)" % val
                    break
            LOGGER.info("%s %s - %s %s", method, path, status, content_length)
            return start_response(status, headers, exc_info)

        return wsgi_app(environ, log_response)

    return handle


if __name__ == "__main__":
    serve(log_access_factory(main(ping_connections=True)), host="0.0.0.0", port=8000)
