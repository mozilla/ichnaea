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

    # The last part of these keys is a counter than can be incremented
    # whenever the contents/structure of the cache changes. This allows
    # for easy `cache-busting'.
    cache_keys = {
        'downloads': b'cache:downloads:3',
        'fallback_blue': b'cache:fallback:blue:',
        'fallback_cell': b'cache:fallback:cell:',
        'fallback_wifi': b'cache:fallback:wifi:',
        'leaders': b'cache:leaders:2',
        'leaders_weekly': b'cache:leaders_weekly:2',
        'stats': b'cache:stats:3',
        'stats_regions': b'cache:stats_regions:4',
        'stats_blue_json': b'cache:stats_blue_json:2',
        'stats_cell_json': b'cache:stats_cell_json:2',
        'stats_wifi_json': b'cache:stats_wifi_json:2',
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
