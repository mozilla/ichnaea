from uuid import uuid4

from ichnaea.queue import DataQueue


class TestDataQueue(object):
    def _make_queue(self, redis, batch=0, compress=False, json=True):
        return DataQueue(uuid4().hex, redis, batch=batch, compress=compress, json=json)

    def test_objects(self, redis):
        queue = self._make_queue(redis)
        items = [{"a": 1}, "b", 2]
        queue.enqueue(items)
        assert queue.dequeue() == items

    def test_binary(self, redis):
        queue = self._make_queue(redis, json=False)
        items = [b"\x00ab", b"123"]
        queue.enqueue(items)
        assert queue.dequeue() == items

    def test_compress(self, redis):
        queue = self._make_queue(redis, compress=True)
        items = [{"a": 1}, "b", 2]
        queue.enqueue(items)
        assert queue.dequeue() == items

    def test_compress_binary(self, redis):
        queue = self._make_queue(redis, compress=True, json=False)
        items = [b"\x00ab", b"123"]
        queue.enqueue(items)
        assert queue.dequeue() == items

    def test_batch(self, redis):
        queue = self._make_queue(redis, batch=3)
        queue.enqueue([1, 2, 3, 4, 5, 6])
        first = queue.dequeue()
        assert first == [1, 2, 3]
        second = queue.dequeue(batch=2)
        assert second == [4, 5]
        assert queue.dequeue() == [6]

    def test_pipe(self, redis):
        queue = self._make_queue(redis)
        pipe = redis.pipeline()
        queue.enqueue([1, 2, 3], pipe=pipe)
        assert queue.size() == 0
        pipe.execute()
        assert queue.size() == 3

    def test_ready(self, redis):
        queue = self._make_queue(redis, batch=4)
        assert not queue.ready()
        queue.enqueue(["a", "b", "c"])
        assert not queue.ready()
        queue.enqueue(["d"])
        assert queue.ready()

    def test_ready_ttl(self, redis):
        queue = self._make_queue(redis, batch=4)
        queue.enqueue(["a", "b", "c"])
        assert not queue.ready()
        redis.expire(queue.key, 70000)
        assert queue.ready()

    def test_size(self, redis):
        queue = self._make_queue(redis)
        assert queue.size() == 0
        queue.enqueue(["a", "b"])
        assert queue.size() == 2
        queue.dequeue()
        assert queue.size() == 0
