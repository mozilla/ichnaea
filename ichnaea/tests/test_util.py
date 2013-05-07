from unittest import TestCase
from ichnaea.util import _is_true


class TestUtils(TestCase):

    def test_is_true(self):
        self.assertTrue(_is_true('1'))
        self.assertTrue(_is_true('true'))
        self.assertTrue(_is_true('True'))
        self.assertTrue(_is_true(True))
        self.assertFalse(_is_true(False))
        self.assertFalse(_is_true('false'))
