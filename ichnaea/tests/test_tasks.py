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
