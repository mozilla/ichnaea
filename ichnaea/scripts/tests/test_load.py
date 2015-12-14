from ichnaea.scripts import load
from ichnaea.tests.base import TestCase


class LoadTestCase(TestCase):

    def test_compiles(self):
        self.assertTrue(hasattr(load, 'console_entry'))
