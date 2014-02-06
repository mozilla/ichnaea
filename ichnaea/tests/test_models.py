import datetime

from sqlalchemy.exc import IntegrityError

from ichnaea.tests.base import DBTestCase


class TestCell(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import Cell
        return Cell(**kw)

    def test_constructor(self):
        cell = self._make_one()
        self.assertTrue(cell.id is None)
        self.assertEqual(cell.new_measures, 0)
        self.assertEqual(cell.total_measures, 0)

    def test_fields(self):
        cell = self._make_one(
            lat=12345678, lon=23456789, mcc=100, mnc=5, lac=12345, cid=234567,
            new_measures=2, total_measures=15,
        )
        session = self.db_master_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.cid, 234567)
        self.assertEqual(result.new_measures, 2)
        self.assertEqual(result.total_measures, 15)


class TestCellMeasure(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import CellMeasure
        return CellMeasure(**kw)

    def test_constructor(self):
        cell = self._make_one()
        self.assertTrue(cell.id is None)

    def test_fields(self):
        cell = self._make_one(lat=12345678, lon=23456789, radio=0, mcc=100,
                              mnc=5, lac=12345, cid=234567, asu=26,
                              signal=-61, ta=10)
        session = self.db_master_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.measure_id, 0)
        self.assertTrue(isinstance(result.created, datetime.datetime))
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.lon, 23456789)
        self.assertEqual(result.radio, 0)
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 12345)
        self.assertEqual(result.cid, 234567)
        self.assertEqual(result.asu, 26)
        self.assertEqual(result.signal, -61)
        self.assertEqual(result.ta, 10)


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
            key=key, lat=12345678, lon=23456789, range=200,
            new_measures=2, total_measures=15,
        )
        session = self.db_master_session
        session.add(wifi)
        session.commit()

        result = session.query(wifi.__class__).first()
        self.assertEqual(result.key, key)
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.lon, 23456789)
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
        self.assertTrue(wifi.created is not None)

    def test_fields(self):
        key = "3680873e9b83"
        wifi = self._make_one(key=key)
        session = self.db_master_session
        session.add(wifi)
        session.commit()

        result = session.query(wifi.__class__).first()
        self.assertEqual(result.key, key)
        self.assertTrue(isinstance(result.created, datetime.datetime))

    def test_unique_key(self):
        key = "3680873e9b83"
        wifi1 = self._make_one(key=key)
        session = self.db_master_session
        session.add(wifi1)
        session.commit()

        wifi2 = self._make_one(key=key)
        session.add(wifi2)
        self.assertRaises(IntegrityError, session.commit)


class TestWifiMeasure(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import WifiMeasure
        return WifiMeasure(**kw)

    def test_constructor(self):
        wifi = self._make_one()
        self.assertTrue(wifi.id is None)

    def test_fields(self):
        key = "3680873e9b83"
        wifi = self._make_one(
            lat=12345678, lon=23456789, key=key, channel=2412, signal=-45)
        session = self.db_master_session
        session.add(wifi)
        session.commit()

        result = session.query(wifi.__class__).first()
        self.assertEqual(result.measure_id, 0)
        self.assertTrue(isinstance(result.created, datetime.datetime))
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.lon, 23456789)
        self.assertEqual(result.key, key)
        self.assertEqual(result.channel, 2412)
        self.assertEqual(result.signal, -45)


class TestMeasure(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import Measure
        return Measure(**kw)

    def test_constructor(self):
        measure = self._make_one()
        self.assertTrue(measure.id is None)

    def test_fields(self):
        measure = self._make_one(lat=12345678, lon=23456789)
        session = self.db_master_session
        session.add(measure)
        session.commit()

        result = session.query(measure.__class__).first()
        self.assertTrue(isinstance(result.created, datetime.datetime))
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.lon, 23456789)
