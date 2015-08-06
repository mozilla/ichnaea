"""Setup and configuration of a HTTP/S request pool."""

import certifi
from requests.adapters import HTTPAdapter
from requests.sessions import Session


def configure_http_session(size=20, _session=None):
    """
    Return a :class:`requests.Session` object configured with
    a :class:`requests.adapters.HTTPAdapter` (connection pool)
    for http and https connections.

    :param size: The connection pool and maximum size.
    :type size: int

    :param _session: Test-only hook to provide a pre-configured session.
    """
    if _session is not None:
        return _session

    adapter = HTTPAdapter(pool_connections=size, pool_maxsize=size)
    session = Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.verify = certifi.where()
    return session
