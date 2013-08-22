from sqlalchemy.orm.exc import FlushError

from ichnaea.db import Measure
from ichnaea.tests.base import CeleryTestCase


class TestTasks(CeleryTestCase):

    def test_add_measure(self):
        from ichnaea.tasks import add_measure
        result = add_measure.delay(lat=12345678, lon=23456789)
        self.assertTrue(result.get() is None)
        self.assertTrue(result.successful())

        session = self.db_master_session
        result = session.query(Measure).first()
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.lon, 23456789)

    def test_add_measure_fail(self):
        from ichnaea.tasks import add_measure
        counter = [0]
        self.assertRaises(
            FlushError, add_measure.delay, fail_counter=counter)
        self.assertEqual(counter[0], 4)

        session = self.db_master_session
        result = session.query(Measure).count()
        self.assertEqual(result, 0)
