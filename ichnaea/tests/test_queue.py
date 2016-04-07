from uuid import uuid4

from ichnaea.queue import DataQueue
from ichnaea.tests.base import RedisTestCase


class TestDataQueue(RedisTestCase):

    def _make_queue(self, batch=0, compress=False, json=True):
        return DataQueue(uuid4().hex, self.redis_client,
                         batch=batch, compress=compress, json=json)

    def test_objects(self):
        queue = self._make_queue()
        items = [{'a': 1}, 'b', 2]
        queue.enqueue(items)
        self.assertEqual(queue.dequeue(), items)

    def test_binary(self):
        queue = self._make_queue(json=False)
        items = [b'\x00ab', b'123']
        queue.enqueue(items)
        self.assertEqual(queue.dequeue(), items)

    def test_compress(self):
        queue = self._make_queue(compress=True)
        items = [{'a': 1}, 'b', 2]
        queue.enqueue(items)
        self.assertEqual(queue.dequeue(), items)

    def test_compress_binary(self):
        queue = self._make_queue(compress=True, json=False)
        items = [b'\x00ab', b'123']
        queue.enqueue(items)
        self.assertEqual(queue.dequeue(), items)

    def test_batch(self):
        queue = self._make_queue(batch=3)
        queue.enqueue([1, 2, 3, 4, 5, 6])
        first = queue.dequeue()
        self.assertEqual(first, [1, 2, 3])
        second = queue.dequeue(batch=2)
        self.assertEqual(second, [4, 5])
        self.assertEqual(queue.dequeue(), [6])

    def test_pipe(self):
        queue = self._make_queue()
        pipe = self.redis_client.pipeline()
        queue.enqueue([1, 2, 3], pipe=pipe)
        self.assertEqual(queue.size(), 0)
        pipe.execute()
        self.assertEqual(queue.size(), 3)

    def test_ready(self):
        queue = self._make_queue(batch=4)
        self.assertFalse(queue.ready())
        queue.enqueue(['a', 'b', 'c'])
        self.assertFalse(queue.ready())
        queue.enqueue(['d'])
        self.assertTrue(queue.ready())

    def test_ready_ttl(self):
        queue = self._make_queue(batch=4)
        queue.enqueue(['a', 'b', 'c'])
        self.assertFalse(queue.ready())
        self.redis_client.expire(queue.key, 70000)
        self.assertTrue(queue.ready())

    def test_size(self):
        queue = self._make_queue()
        self.assertEqual(queue.size(), 0)
        queue.enqueue(['a', 'b'])
        self.assertEqual(queue.size(), 2)
        queue.dequeue()
        self.assertEqual(queue.size(), 0)
