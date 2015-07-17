from collections import namedtuple
from datetime import date, datetime
import uuid

import pytz

from ichnaea.internaljson import (
    internal_dumps,
    internal_loads,
)
from ichnaea.tests.base import TestCase
from ichnaea import util


class TestInternalJSON(TestCase):

    def test_date_dump(self):
        data = internal_dumps({'d': date(2012, 5, 17)})
        self.assertTrue('__date__' in data)

    def test_date_roundtrip(self):
        test_date = date(2012, 5, 17)
        data = internal_loads(internal_dumps({'d': test_date}))
        self.assertEqual(test_date, data['d'])

    def test_datetime_dump(self):
        data = internal_dumps({'d': datetime(2012, 5, 17, 14, 28, 56)})
        self.assertTrue('__datetime__' in data)

    def test_datetime_roundtrip(self):
        test_date = datetime(2012, 5, 17, 14, 28, 56)
        data = internal_loads(internal_dumps({'d': test_date}))
        self.assertEqual(test_date.replace(tzinfo=pytz.UTC), data['d'])

    def test_datetime_utc_roundtrip(self):
        test_date = util.utcnow()
        data = internal_loads(internal_dumps({'d': test_date}))
        self.assertEqual(test_date, data['d'])

    def test_datetime_us_roundtrip(self):
        us = pytz.timezone('US/Eastern')
        test_date = datetime(2012, 5, 17, 14, 28, 56, tzinfo=us)
        data = internal_loads(internal_dumps({'d': test_date}))
        self.assertEqual(test_date, data['d'])
        self.assertTrue(data['d'].tzinfo is pytz.utc)

    def test_namedtuple(self):
        Named = namedtuple('Named', 'one two')
        data = internal_loads(internal_dumps({'d': Named(one=1, two=[2])}))
        self.assertEqual(data['d'], {'one': 1, 'two': [2]})

    def test_uuid1(self):
        data = internal_dumps({'d': uuid.uuid1()})
        self.assertTrue('__uuid__' in data)

    def test_uuid4(self):
        data = internal_dumps({'d': uuid.uuid4()})
        self.assertTrue('__uuid__' in data)

    def test_uuid1_roundtrip(self):
        test_uuid = uuid.uuid1()
        data = internal_loads(internal_dumps({'d': test_uuid}))
        self.assertEqual(data['d'], test_uuid)
        self.assertEqual(data['d'].version, 1)

    def test_uuid4_roundtrip(self):
        test_uuid = uuid.uuid4()
        data = internal_loads(internal_dumps({'d': test_uuid}))
        self.assertEqual(data['d'], test_uuid)
        self.assertEqual(data['d'].version, 4)
