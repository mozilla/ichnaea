"""
Functionality related to custom Redis based queues.
"""

import re

from six.moves.urllib.parse import urlparse

from ichnaea.cache import redis_pipeline
from ichnaea.internaljson import (
    internal_dumps,
    internal_loads,
)
from ichnaea import util

EXPORT_QUEUE_PREFIX = 'queue_export_'
WHITESPACE = re.compile('\s', flags=re.UNICODE)


class BaseQueue(object):
    """
    A Redis based queue which stores binary or JSON encoded items
    in lists.

    The lists maintain a TTL value corresponding to the time data has
    been last put into the queue.

    The enough_data function checks if a queue has either more than a
    certain batch number of items in it, or if the last time it has
    seen new data was more than an hour ago.
    """

    queue_ttl = 86400  #: Maximum TTL value for the Redis list.
    queue_max_age = 3600  #: Maximum age that data can sit in the queue.

    def __init__(self, name, redis_client, compress=False):
        self.name = name
        self.redis_client = redis_client
        self.compress = compress

    def _dequeue(self, queue_key, batch, json=True):
        with self.redis_client.pipeline() as pipe:
            pipe.multi()
            pipe.lrange(queue_key, 0, batch - 1)
            if batch != 0:
                pipe.ltrim(queue_key, batch, -1)
            else:
                # special case for deleting everything
                pipe.ltrim(queue_key, 1, 0)
            result = pipe.execute()[0]

            if self.compress:
                result = [util.decode_gzip(item) for item in result]
            if json:
                # BBB replace with simplejson
                result = [internal_loads(item) for item in result]

        return result

    def _push(self, pipe, items, queue_key, batch=100):
        if items:
            pipe.expire(queue_key, self.queue_ttl)

        while items:
            pipe.lpush(queue_key, *items[:batch])
            items = items[batch:]

    def _enqueue(self, items, queue_key, batch=100, pipe=None, json=True):
        if json:
            # BBB replace with simplejson
            items = [str(internal_dumps(item)) for item in items]

        if self.compress:
            items = [util.encode_gzip(item) for item in items]
        elif not json:
            # make a copy, since _push is modifying the list in-place
            items = list(items)

        if pipe is not None:
            self._push(pipe, items, queue_key, batch=batch)
        else:
            with redis_pipeline(self.redis_client) as pipe:
                self._push(pipe, items, queue_key, batch=batch)

    def _size_age(self, queue_key):
        with self.redis_client.pipeline() as pipe:
            pipe.ttl(queue_key)
            pipe.llen(queue_key)
            ttl, size = pipe.execute()
        if ttl < 0:
            age = -1
        else:
            age = min(self.queue_ttl - ttl, 0)
        return (size, age)


class DataQueue(BaseQueue):

    def __init__(self, name, redis_client, queue_key, compress=False):
        super(DataQueue, self).__init__(name, redis_client, compress=compress)
        self._queue_key = queue_key

    @property
    def monitor_name(self):
        return self.queue_key()

    def queue_key(self):
        return self._queue_key

    def dequeue(self, batch=100, json=True):
        return self._dequeue(self.queue_key(), batch, json=json)

    def enqueue(self, items, batch=100, pipe=None, json=True):
        self._enqueue(items, self.queue_key(),
                      batch=batch, pipe=pipe, json=json)

    def enough_data(self, batch=0):
        size, age = self.size_age()
        return bool(size > 0 and (size >= batch or age >= self.queue_max_age))

    def size(self):
        return self._size_age(self.queue_key())[0]

    def size_age(self):
        return self._size_age(self.queue_key())


class ExportQueue(BaseQueue):

    def __init__(self, name, redis_client, settings, compress=False):
        super(ExportQueue, self).__init__(
            name, redis_client, compress=compress)
        self.settings = settings
        self.batch = int(settings.get('batch', 0))
        self.metadata = bool(settings.get('metadata', False))
        self.url = settings.get('url', '') or ''
        self.scheme = urlparse(self.url).scheme
        self.uploader_type = self.configure_uploader(self.scheme)
        skip_keys = WHITESPACE.split(settings.get('skip_keys', ''))
        self.skip_keys = tuple([key for key in skip_keys if key])

    @staticmethod
    def configure_uploader(scheme):
        from ichnaea.data import upload
        from ichnaea.data.internal import InternalUploader

        uploaders = {
            'http': upload.GeosubmitUploader,
            'https': upload.GeosubmitUploader,
            'internal': InternalUploader,
            's3': upload.S3Uploader,
        }
        return uploaders.get(scheme, None)

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

    def dequeue(self, queue_key, batch=100, json=True):
        return self._dequeue(queue_key, batch, json=json)

    def enqueue(self, items, queue_key, batch=100, pipe=None, json=True):
        self._enqueue(items, queue_key=queue_key,
                      batch=batch, pipe=pipe, json=json)

    def enough_data(self, queue_key):
        size, age = self.size_age(queue_key)
        return bool(size > 0 and (
            size >= self.batch or age >= self.queue_max_age))

    def size(self, queue_key):
        return self._size_age(queue_key)[0]

    def size_age(self, queue_key):
        return self._size_age(queue_key)
