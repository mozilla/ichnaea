from collections import namedtuple
from datetime import date, datetime, timedelta
import sys

import pytz

from ichnaea.customjson import (
    dumps,
    kombu_dumps,
    kombu_loads,
    Renderer,
)
from ichnaea.tests.base import TestCase
from ichnaea import util


class TestRenderer(TestCase):

    def setUp(self):
        self.render = Renderer()(None)

    def test_basic(self):
        self.assertEqual(self.render({'a': 1}, {}), '{"a": 1}')

    def test_date(self):
        self.assertEqual(self.render({'d': date(2012, 5, 17)}, {}),
                         '{"d": "2012-05-17"}')

    def test_datetime(self):
        self.assertEqual(
            self.render({'d': datetime(2012, 5, 17, 14, 28, 56)}, {}),
            '{"d": "2012-05-17T14:28:56.000000"}')

    def test_high_precision(self):
        self.assertEqual(self.render({'accuracy': 12.345678}, {}),
                         '{"accuracy": 12.345678}')

    def test_no_special_treatment_without_accuracy_field(self):
        # This tests that, when we're rendering a dict to json with no
        # 'accuracy' field, we do not apply any special processing to
        # floats (namely, we get ugly float representation on python2.6)
        if sys.version_info < (2, 7):
            expect = '{"z": 12.345677999999999}'
        else:
            expect = '{"z": 12.345678}'
        self.assertEqual(self.render({'z': 12.345678}, {}), expect)

    def test_low_precision(self):
        self.assertEqual(self.render({'accuracy': 12.34}, {}),
                         '{"accuracy": 12.34}')

    def test_error(self):
        self.assertRaises(TypeError, dumps, timedelta(days=1))


class TestKombuJson(TestCase):

    def test_date_dump(self):
        data = kombu_dumps({'d': date(2012, 5, 17)})
        self.assertTrue('__date__' in data)

    def test_date_roundtrip(self):
        test_date = date(2012, 5, 17)
        data = kombu_loads(kombu_dumps({'d': test_date}))
        self.assertEqual(test_date, data['d'])

    def test_datetime_dump(self):
        data = kombu_dumps({'d': datetime(2012, 5, 17, 14, 28, 56)})
        self.assertTrue('__datetime__' in data)

    def test_datetime_roundtrip(self):
        test_date = datetime(2012, 5, 17, 14, 28, 56)
        data = kombu_loads(kombu_dumps({'d': test_date}))
        self.assertEqual(test_date.replace(tzinfo=pytz.UTC), data['d'])

    def test_datetime_utc_roundtrip(self):
        test_date = util.utcnow()
        data = kombu_loads(kombu_dumps({'d': test_date}))
        self.assertEqual(test_date, data['d'])

    def test_datetime_us_roundtrip(self):
        us = pytz.timezone('US/Eastern')
        test_date = datetime(2012, 5, 17, 14, 28, 56, tzinfo=us)
        data = kombu_loads(kombu_dumps({'d': test_date}))
        self.assertEqual(test_date, data['d'])
        self.assertTrue(data['d'].tzinfo is pytz.utc)

    def test_namedtuple(self):
        Named = namedtuple('Named', 'one two')
        data = kombu_loads(kombu_dumps({'d': Named(one=1, two=[2])}))
        self.assertEqual(data['d'], {'one': 1, 'two': [2]})
