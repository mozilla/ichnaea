import datetime
from Queue import Queue


class TimedQueue(Queue):
    """A Queue with an age for the first item
    """
    def __init__(self, maxsize=1000):
        Queue.__init__(self, maxsize)
        self._first_put_time = None

    @property
    def age(self):
        if self._first_put_time is None:
            return datetime.timedelta(seconds=0)
        return datetime.datetime.utcnow() - self._first_put_time

    def put(self, item, block=True, timeout=None):
        # first item
        if self.empty():
            self._first_put_time = datetime.datetime.utcnow()
        return Queue.put(self, item, block=block, timeout=timeout)

    def get(self, block=True, timeout=None):
        res = Queue.get(self, block=block, timeout=timeout)
        if self.empty():
            self._first_put_time = None
        return res
