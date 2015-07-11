"""
Holds global web application state and the WSGI handler.
"""

from ichnaea.config import read_config
from ichnaea.webapp.config import main

_APP = None  #: Internal module global holding the runtime web app.


def wsgi_app(environ, start_response):  # pragma: no cover
    """
    Actual WSGI application endpoint, used on the command line via:

    .. code-block:: bash

        bin/gunicorn -c ichnaea.webapp.settings ichnaea.webapp.app:wsgi_app

    At startup reads the app config and calls
    :func:`ichnaea.webapp.config.main` once to setup the web app stored
    in the :data:`ichnaea.webapp.app._APP` global.
    """
    global _APP

    if _APP is None:
        conf = read_config()
        _APP = main(conf, ping_connections=True)
        if environ is None and start_response is None:
            # Called as part of gunicorn's post_worker_init
            return _APP

    return _APP(environ, start_response)
