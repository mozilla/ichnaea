from unittest import TestCase
from datetime import date
from datetime import datetime
from datetime import timedelta
import sys

from ichnaea.customjson import (
    dumps,
    Renderer
)


class TestRenderer(TestCase):

    def _make_one(self):
        return Renderer()(None)

    def test_basic(self):
        render = self._make_one()
        self.assertEqual(render({'a': 1}, {}), '{"a": 1}')

    def test_date(self):
        render = self._make_one()
        self.assertEqual(render({'d': date(2012, 5, 17)}, {}),
                         '{"d": "2012-05-17"}')

    def test_datetime(self):
        render = self._make_one()
        self.assertEqual(render({'d': datetime(2012, 5, 17, 14, 28, 56)}, {}),
                         '{"d": "2012-05-17T14:28:56.000000"}')

    def test_high_precision(self):
        render = self._make_one()
        d = 12.345678
        self.assertEqual(render({'accuracy': d}, {}),
                         '{"accuracy": 12.345678}')

    def test_no_special_treatment_without_accuracy_field(self):
        # This tests that, when we're rendering a dict to json with no
        # 'accuracy' field, we do not apply any special processing to
        # floats (namely, we get ugly float representation on python2.6)
        render = self._make_one()
        d = 12.345678
        if sys.version_info < (2, 7):
            expect = '{"z": 12.345677999999999}'
        else:
            expect = '{"z": 12.345678}'
        self.assertEqual(render({'z': d}, {}), expect)

    def test_low_precision(self):
        render = self._make_one()
        d = 12.34
        self.assertEqual(render({'accuracy': d}, {}), '{"accuracy": 12.34}')

    def test_error(self):
        self.assertRaises(TypeError, dumps, timedelta(days=1))
