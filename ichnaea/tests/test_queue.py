from ichnaea.queue import TimedQueue
from unittest import TestCase
import datetime


class TestQueue(TestCase):

    def test_age_is_null(self):
        # if we don't insert anything, the age is 0
        q = TimedQueue()
        zero = datetime.timedelta(seconds=0)
        self.assertEquals(q.age, zero)

    def test_age_works_if_items_present(self):
        q = TimedQueue()
        q.put(1)
        q.put(2)
        zero = datetime.timedelta(seconds=0)
        self.assertNotEquals(q.age, zero)

    def test_age_is_null_when_items_removed(self):
        q = TimedQueue()
        q.put(1)
        q.get()
        zero = datetime.timedelta(seconds=0)
        self.assertEquals(q.age, zero)
