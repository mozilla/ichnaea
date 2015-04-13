from ichnaea.config import read_config
from ichnaea.webapp.config import main

_APP = None


def wsgi_app(environ, start_response):  # pragma: no cover
    # Actual WSGI application endpoint, used on the command line via:
    # bin/gunicorn -c ichnaea.webapp.settings ichnaea.webapp.app:wsgi_app
    global _APP

    if _APP is None:
        conf = read_config()
        # Signal this call was made as part of app initialization
        _APP = main({}, conf, init=True)
        if environ is None and start_response is None:
            # Called as part of gunicorn's post_worker_init
            return _APP

    return _APP(environ, start_response)
