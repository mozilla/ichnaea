from unittest2 import TestCase


class TestTasks(TestCase):

    def test_add(self):
        from ichnaea.tasks import add
        result = add.delay(1, 3)
        self.assertEqual(result.get(), 4)
        self.assertTrue(result.successful())
