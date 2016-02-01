"""
Functionality related to using Redis as a cache and a queue.
"""

from contextlib import contextmanager

import redis
from redis.exceptions import RedisError
from six.moves.urllib.parse import urlparse


def configure_redis(cache_url, _client=None):
    """
    Configure and return a :class:`~ichnaea.cache.RedisClient` instance.

    :param _client: Test-only hook to provide a pre-configured client.
    """
    if cache_url is None or _client is not None:
        return _client

    url = urlparse(cache_url)
    netloc = url.netloc.split(':')
    host = netloc[0]
    if len(netloc) > 1:
        port = int(netloc[1])
    else:  # pragma: no cover
        port = 6379
    if len(url.path) > 1:
        db = int(url.path[1:])
    else:  # pragma: no cover
        db = 0
    pool = redis.ConnectionPool(
        max_connections=20,
        host=host,
        port=port,
        db=db,
        socket_timeout=30.0,
        socket_connect_timeout=60.0,
        socket_keepalive=True,
    )
    return RedisClient(connection_pool=pool)


@contextmanager
def redis_pipeline(redis_client, execute=True):
    """
    Return a Redis pipeline usable as a context manager.

    :param execute: Should the pipeline be executed or aborted at the end?
    :type execute: bool
    """
    with redis_client.pipeline() as pipe:
        yield pipe
        if execute:
            pipe.execute()


class RedisClient(redis.StrictRedis):
    """A strict pingable RedisClient."""

    cache_keys = {
        'downloads': b'cache:downloads',
        'fallback_blue': b'cache:fallback:blue:',
        'fallback_cell': b'cache:fallback:cell:',
        'fallback_wifi': b'cache:fallback:wifi:',
        'leaders': b'cache:leaders',
        'leaders_weekly': b'cache:leaders_weekly',
        'stats': b'cache:stats',
        'stats_regions': b'cache:stats_regions:2',
        'stats_cell_json': b'cache:stats_cell_json',
        'stats_wifi_json': b'cache:stats_wifi_json',
    }

    def ping(self):
        """
        Ping the Redis server. On success return `True`, otherwise `False`.
        """
        try:
            self.execute_command('PING')
        except RedisError:
            return False
        return True
