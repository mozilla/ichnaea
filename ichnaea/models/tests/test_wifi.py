import datetime

from sqlalchemy.exc import IntegrityError

from ichnaea.tests.base import DBTestCase


class TestWifi(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import Wifi
        return Wifi(**kw)

    def test_constructor(self):
        wifi = self._make_one()
        self.assertTrue(wifi.key is None)
        self.assertEqual(wifi.new_measures, 0)
        self.assertEqual(wifi.total_measures, 0)

    def test_fields(self):
        key = "3680873e9b83"
        wifi = self._make_one(
            key=key, lat=1.2345678, lon=2.3456789, range=200,
            new_measures=2, total_measures=15,
        )
        session = self.db_master_session
        session.add(wifi)
        session.commit()

        result = session.query(wifi.__class__).first()
        self.assertEqual(result.key, key)
        self.assertEqual(result.lat, 1.2345678)
        self.assertEqual(result.lon, 2.3456789)
        self.assertEqual(result.range, 200)
        self.assertEqual(result.new_measures, 2)
        self.assertEqual(result.total_measures, 15)


class TestWifiBlacklist(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import WifiBlacklist
        return WifiBlacklist(**kw)

    def test_constructor(self):
        wifi = self._make_one()
        self.assertTrue(wifi.key is None)
        self.assertTrue(wifi.time is not None)
        self.assertTrue(wifi.count is not None)

    def test_fields(self):
        key = "3680873e9b83"
        wifi = self._make_one(key=key)
        session = self.db_master_session
        session.add(wifi)
        session.commit()

        result = session.query(wifi.__class__).first()
        self.assertEqual(result.key, key)
        self.assertTrue(isinstance(result.time, datetime.datetime))
        self.assertTrue(isinstance(result.count, int))

    def test_unique_key(self):
        key = "3680873e9b83"
        wifi1 = self._make_one(key=key)
        session = self.db_master_session
        session.add(wifi1)
        session.commit()

        wifi2 = self._make_one(key=key)
        session.add(wifi2)
        self.assertRaises(IntegrityError, session.commit)
