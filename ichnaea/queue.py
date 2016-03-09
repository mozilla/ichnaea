"""
Functionality related to custom Redis based queues.
"""

import simplejson

from ichnaea.cache import redis_pipeline
from ichnaea import util


class DataQueue(object):
    """
    A Redis based queue which stores binary or JSON encoded items
    in lists. The queue uses a single static queue key.

    The lists maintain a TTL value corresponding to the time data has
    been last put into the queue.
    """

    queue_ttl = 86400  #: Maximum TTL value for the Redis list.
    queue_max_age = 3600  #: Maximum age that data can sit in the queue.

    def __init__(self, name, redis_client, queue_key, compress=False):
        self.name = name
        self.redis_client = redis_client
        self.queue_key = queue_key
        self.compress = compress

    def dequeue(self, batch=100, json=True):
        """
        Get batch number of items from the queue, optionally decode
        all items from JSON.
        """
        with self.redis_client.pipeline() as pipe:
            pipe.multi()
            pipe.lrange(self.queue_key, 0, batch - 1)
            if batch != 0:
                pipe.ltrim(self.queue_key, batch, -1)
            else:
                # special case for deleting everything
                pipe.ltrim(self.queue_key, 1, 0)
            result = pipe.execute()[0]

            if self.compress:
                result = [util.decode_gzip(item, encoding=None)
                          for item in result]
            if json:
                # simplejson.loads returns Unicode strings
                result = [simplejson.loads(item, encoding='utf-8')
                          for item in result]

        return result

    def _push(self, pipe, items, batch=100):
        for i in range(0, len(items), batch):
            pipe.rpush(self.queue_key, *items[i:i + batch])

        # expire key after it was created by rpush
        pipe.expire(self.queue_key, self.queue_ttl)

    def enqueue(self, items, batch=100, pipe=None, json=True):
        """
        Put items into the queue, optionally encode all items as JSON.

        The items will be pushed into Redis as part of a single (given)
        pipe in batches corresponding to the given batch argument.
        """
        if json:
            # simplejson.dumps returns Unicode strings
            items = [simplejson.dumps(item, encoding='utf-8').encode('utf-8')
                     for item in items]

        if self.compress:
            items = [util.encode_gzip(item, encoding=None) for item in items]

        if pipe is not None:
            self._push(pipe, items, batch=batch)
        else:
            with redis_pipeline(self.redis_client) as pipe:
                self._push(pipe, items, batch=batch)

    @property
    def monitor_name(self):
        """Queue name used in monitoring metrics."""
        return self.queue_key

    def ready(self, batch=0):
        """
        Returns True if the queue has either more than a certain
        batch number of items in it, or if the last time it has seen
        new data was more than an hour ago (queue_max_age).
        """
        with self.redis_client.pipeline() as pipe:
            pipe.ttl(self.queue_key)
            pipe.llen(self.queue_key)
            ttl, size = pipe.execute()
        if ttl < 0:
            age = -1
        else:
            age = max(self.queue_ttl - ttl, 0)
        return bool(size > 0 and (size >= batch or age >= self.queue_max_age))

    def size(self):
        """Return the size of the queue."""
        return self.redis_client.llen(self.queue_key)
