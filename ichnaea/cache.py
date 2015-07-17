"""
Functionality related to using Redis as a cache and a queue.
"""

from contextlib import contextmanager
import re

import redis
from redis.connection import SocketBuffer
from redis.exceptions import RedisError
from six.moves.urllib.parse import urlparse

from ichnaea.customjson import (
    kombu_dumps,
    kombu_loads,
)

EXPORT_QUEUE_PREFIX = 'queue_export_'
WHITESPACE = re.compile('\s', flags=re.UNICODE)


# workaround for https://github.com/andymccurdy/redis-py/issues/633

def close(self):
    try:
        self.purge()
    except ValueError:  # pragma: no cover
        pass
    self._buffer.close()
    self._buffer = None
    self._sock = None

SocketBuffer._old_close = SocketBuffer.close
SocketBuffer.close = close


def configure_redis(redis_url, _client=None):
    """
    Configure and return a :class:`~ichnaea.cache.RedisClient` instance.

    :param _client: Test-only hook to provide a pre-configured client.
    """
    if redis_url is None or _client is not None:
        return _client

    url = urlparse(redis_url)
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
        socket_timeout=10.0,
        socket_connect_timeout=30.0,
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

    def ping(self):
        """
        Ping the Redis server. On success return `True`, otherwise `False`.
        """
        try:
            self.execute_command('PING')
        except RedisError:
            return False
        return True


class BaseQueue(object):

    def __init__(self, name, redis_client):
        self.name = name
        self.redis_client = redis_client

    def _dequeue(self, queue_key, batch):
        with self.redis_client.pipeline() as pipe:
            pipe.multi()
            pipe.lrange(queue_key, 0, batch - 1)
            if batch != 0:
                pipe.ltrim(queue_key, batch, -1)
            else:
                # special case for deleting everything
                pipe.ltrim(queue_key, 1, 0)
            result = [kombu_loads(item) for item in pipe.execute()[0]]
        return result

    def _push(self, pipe, items, queue_key, batch=100, expire=False):
        if items and expire:
            pipe.expire(queue_key, expire)

        while items:
            pipe.lpush(queue_key, *items[:batch])
            items = items[batch:]

    def _enqueue(self, items, queue_key, batch=100, expire=False, pipe=None):
        data = [str(kombu_dumps(item)) for item in items]
        if pipe is not None:
            self._push(pipe, data, queue_key, batch=batch, expire=expire)
        else:
            with redis_pipeline(self.redis_client) as pipe:
                self._push(pipe, data, queue_key, batch=batch, expire=expire)

    def _size(self, queue_key):
        return self.redis_client.llen(queue_key)


class DataQueue(BaseQueue):

    def __init__(self, name, redis_client, queue_key):
        BaseQueue.__init__(self, name, redis_client)
        self._queue_key = queue_key

    @property
    def monitor_name(self):
        return self.queue_key()

    def queue_key(self):
        return self._queue_key

    def dequeue(self, batch=100):
        return self._dequeue(self.queue_key(), batch)

    def enqueue(self, items, batch=100, expire=86400, pipe=None):
        self._enqueue(items, self.queue_key(),
                      batch=batch, expire=expire, pipe=pipe)

    def enough_data(self, batch=0):
        queue_size = self.size()
        return (queue_size > 0) and (queue_size >= batch)

    def size(self):
        return self._size(self.queue_key())


class ExportQueue(BaseQueue):

    def __init__(self, name, redis_client, settings):
        BaseQueue.__init__(self, name, redis_client)
        self.settings = settings
        self.batch = int(settings.get('batch', 0))
        self.metadata = bool(settings.get('metadata', False))
        self.url = settings.get('url', '') or ''
        self.scheme = urlparse(self.url).scheme
        skip_keys = WHITESPACE.split(settings.get('skip_keys', ''))
        self.skip_keys = tuple([key for key in skip_keys if key])

    @property
    def monitor_name(self):
        if self.scheme == 's3':
            return None
        return self.queue_key()

    def queue_key(self, api_key=None):
        if self.scheme == 's3':
            if not api_key:
                api_key = 'no_key'
            return self.queue_prefix + api_key
        return EXPORT_QUEUE_PREFIX + self.name

    @property
    def queue_prefix(self):
        if self.scheme == 's3':
            return EXPORT_QUEUE_PREFIX + self.name + ':'
        return None

    def export_allowed(self, api_key):
        return (api_key not in self.skip_keys)

    def dequeue(self, queue_key, batch=100):
        return self._dequeue(queue_key, batch)

    def enqueue(self, items, queue_key, batch=100, expire=False, pipe=None):
        self._enqueue(items, queue_key=queue_key,
                      batch=batch, expire=expire, pipe=pipe)

    def enough_data(self, queue_key):
        queue_size = self.size(queue_key)
        return (queue_size > 0) and (queue_size >= self.batch)

    def size(self, queue_key):
        return self._size(queue_key)
