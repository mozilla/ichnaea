from uuid import uuid4

from ichnaea.queue import DataQueue
from ichnaea.tests.base import RedisTestCase


class TestDataQueue(RedisTestCase):

    def _make_queue(self, compress=False, json=True):
        return DataQueue(uuid4().hex, self.redis_client,
                         compress=compress, json=json)

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
        queue = self._make_queue()
        queue.enqueue([1, 2, 3, 4, 5, 6], batch=3)
        first = queue.dequeue(batch=3)
        self.assertEqual(first, [1, 2, 3])
        second = queue.dequeue(batch=0)
        self.assertEqual(second, [4, 5, 6])
        self.assertEqual(queue.dequeue(batch=0), [])

    def test_pipe(self):
        queue = self._make_queue()
        pipe = self.redis_client.pipeline()
        queue.enqueue([1, 2, 3], pipe=pipe)
        self.assertEqual(queue.size(), 0)
        pipe.execute()
        self.assertEqual(queue.size(), 3)

    def test_monitor_name(self):
        queue = self._make_queue()
        self.assertEqual(queue.monitor_name, queue.key)

    def test_ready(self):
        queue = self._make_queue()
        self.assertFalse(queue.ready())
        self.assertFalse(queue.ready(batch=10))
        queue.enqueue(['a', 'b', 'c'])
        self.assertFalse(queue.ready(batch=4))
        self.assertTrue(queue.ready(batch=3))
        self.assertTrue(queue.ready())

    def test_ready_ttl(self):
        queue = self._make_queue()
        queue.enqueue(['a', 'b', 'c'])
        self.assertFalse(queue.ready(batch=10))
        self.redis_client.expire(queue.key, 70000)
        self.assertTrue(queue.ready(batch=10))
        self.assertTrue(queue.ready(batch=3))
        self.assertTrue(queue.ready())

    def test_size(self):
        queue = self._make_queue()
        self.assertEqual(queue.size(), 0)
        queue.enqueue(['a', 'b'])
        self.assertEqual(queue.size(), 2)
        queue.dequeue()
        self.assertEqual(queue.size(), 0)
