"""
Holds global web application state and the WSGI handler.

You can run this script for a one-process webapp.

Further, you can pass in ``--check`` which will create the app and then exit
making it easier to suss out startup and configuration issues.

"""

import sys
import time

import structlog
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


def log_middleware(wsgi_app):
    """WSGI middleware for logging."""

    def handle(environ, start_response):
        method = environ["REQUEST_METHOD"]
        path = environ.get("PATH_INFO", "")
        start = time.time()
        structlog.threadlocal.clear_threadlocal()
        structlog.threadlocal.bind_threadlocal(http_method=method, http_path=path)

        def log_response(status, headers, exc_info=None):
            duration = time.time() - start
            try:
                status_code = int(status.split()[0])
            except (ValueError, AttributeError, IndexError):
                status_code = status

            params = {
                "http_status": status_code,
                "duration": round(duration, 3),  # Round to milliseconds
            }

            content_length_str = ""
            for key, val in headers:
                if key.lower() == "content-length":
                    try:
                        params["content_length"] = int(val)
                    except ValueError:
                        pass
                    content_length_str = f" ({val})"
                    break

            logger = structlog.get_logger("canonical-log-line")
            logger.info(f"{method} {path} - {status}{content_length_str}", **params)
            return start_response(status, headers, exc_info)

        return wsgi_app(environ, log_response)

    return handle


if __name__ == "__main__":
    if "--check" in sys.argv:
        main(ping_connections=False)
    else:
        serve(
            log_middleware(main(ping_connections=True)),
            host="0.0.0.0",
            port=8000,
            expose_tracebacks=settings("local_dev_env"),
        )
