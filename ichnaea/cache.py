from contextlib import contextmanager
import urlparse

import redis
from redis.exceptions import ConnectionError

from ichnaea.customjson import (
    kombu_dumps,
    kombu_loads,
)

EXPORT_QUEUE_PREFIX = 'queue_export_'
_sentinel = object()


def configure_redis(redis_url, _client=None):
    if redis_url is None or _client is not None:
        return _client
    return redis_client(redis_url)


def redis_client(redis_url):
    url = urlparse.urlparse(redis_url)
    netloc = url.netloc.split(":")
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
    with redis_client.pipeline() as pipe:
        yield pipe
        if execute:
            pipe.execute()


class RedisClient(redis.StrictRedis):

    def ping(self):
        """
        Ping the Redis server, but also catch exceptions.
        """
        try:
            self.execute_command('PING')
        except ConnectionError:
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
            pipe.ltrim(queue_key, batch, -1)
            result = [kombu_loads(item) for item in pipe.execute()[0]]
        return result

    def _push(self, pipe, queue_key, data, batch, expire):
        if data and expire:
            pipe.expire(queue_key, expire)

        while data:
            pipe.lpush(queue_key, *data[:batch])
            data = data[batch:]

    def _enqueue(self, queue_key, items, batch=100, expire=False, pipe=None):
        data = [str(kombu_dumps(item)) for item in items]
        if pipe is not None:
            self._push(pipe, queue_key, data, batch, expire)
        else:
            with redis_pipeline(self.redis_client) as pipe:
                self._push(pipe, queue_key, data, batch, expire)


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
        self._enqueue(self.queue_key(), items,
                      batch=batch, expire=expire, pipe=pipe)


class ExportQueue(BaseQueue):

    def __init__(self, name, redis_client, settings):
        BaseQueue.__init__(self, name, redis_client)
        self.settings = settings
        self.batch = int(settings.get('batch', -1))
        self.metadata = bool(settings.get('metadata', False))
        self.url = settings.get('url', '') or ''
        self.scheme = urlparse.urlparse(self.url).scheme
        self.source_apikey = settings.get('source_apikey', _sentinel)

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
        return (api_key != self.source_apikey)

    def dequeue(self, queue_key, batch=100):
        return self._dequeue(queue_key, batch)

    def enqueue(self, queue_key, items, batch=100, expire=False, pipe=None):
        self._enqueue(queue_key, items,
                      batch=batch, expire=expire, pipe=pipe)

    def size(self, queue_key):
        return self.redis_client.llen(queue_key)
