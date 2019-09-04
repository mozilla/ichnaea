"""
Functionality related to using Redis as a cache and a queue.
"""

from contextlib import contextmanager
from urllib.parse import urlparse

import redis
from redis.exceptions import RedisError

from ichnaea.conf import REDIS_URI


def configure_redis(cache_url=REDIS_URI, _client=None):
    """
    Configure and return a :class:`~ichnaea.cache.RedisClient` instance.

    :param _client: Test-only hook to provide a pre-configured client.
    """
    if _client is not None:
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
        'stats': b'cache:stats:4',
        'stats_regions': b'cache:stats_regions:4',
        'stats_blue_json': b'cache:stats_blue_json:2',
        'stats_cell_json': b'cache:stats_cell_json:3',
        'stats_wifi_json': b'cache:stats_wifi_json:2',
    }

    def close(self):
        self.connection_pool.disconnect()

    def ping(self):
        """
        Ping the Redis server. On success return `True`, otherwise `False`.
        """
        try:
            self.execute_command('PING')
        except RedisError:
            return False
        return True
