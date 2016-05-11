from uuid import uuid4

import pytest

from ichnaea.queue import DataQueue
from ichnaea.tests.base import LogTestCase


@pytest.mark.usefixtures('redis')
class TestDataQueue(LogTestCase):

    def _make_queue(self, batch=0, compress=False, json=True):
        return DataQueue(uuid4().hex, self.redis_client,
                         batch=batch, compress=compress, json=json)

    def test_objects(self):
        queue = self._make_queue()
        items = [{'a': 1}, 'b', 2]
        queue.enqueue(items)
        assert queue.dequeue() == items

    def test_binary(self):
        queue = self._make_queue(json=False)
        items = [b'\x00ab', b'123']
        queue.enqueue(items)
        assert queue.dequeue() == items

    def test_compress(self):
        queue = self._make_queue(compress=True)
        items = [{'a': 1}, 'b', 2]
        queue.enqueue(items)
        assert queue.dequeue() == items

    def test_compress_binary(self):
        queue = self._make_queue(compress=True, json=False)
        items = [b'\x00ab', b'123']
        queue.enqueue(items)
        assert queue.dequeue() == items

    def test_batch(self):
        queue = self._make_queue(batch=3)
        queue.enqueue([1, 2, 3, 4, 5, 6])
        first = queue.dequeue()
        assert first == [1, 2, 3]
        second = queue.dequeue(batch=2)
        assert second == [4, 5]
        assert queue.dequeue() == [6]

    def test_pipe(self):
        queue = self._make_queue()
        pipe = self.redis_client.pipeline()
        queue.enqueue([1, 2, 3], pipe=pipe)
        assert queue.size() == 0
        pipe.execute()
        assert queue.size() == 3

    def test_ready(self):
        queue = self._make_queue(batch=4)
        assert not queue.ready()
        queue.enqueue(['a', 'b', 'c'])
        assert not queue.ready()
        queue.enqueue(['d'])
        assert queue.ready()

    def test_ready_ttl(self):
        queue = self._make_queue(batch=4)
        queue.enqueue(['a', 'b', 'c'])
        assert not queue.ready()
        self.redis_client.expire(queue.key, 70000)
        assert queue.ready()

    def test_size(self):
        queue = self._make_queue()
        assert queue.size() == 0
        queue.enqueue(['a', 'b'])
        assert queue.size() == 2
        queue.dequeue()
        assert queue.size() == 0
