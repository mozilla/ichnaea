import datetime

from sqlalchemy.exc import IntegrityError

from ichnaea.tests.base import DBTestCase


class TestDatabase(DBTestCase):

    def test_constructors(self):
        self.assertEqual(self.db_master.engine.name, 'mysql')
        self.assertEqual(self.db_slave.engine.name, 'mysql')

    def test_sessions(self):
        self.assertTrue(
            self.db_master_session.bind.engine is self.db_master.engine)
        self.assertTrue(
            self.db_slave_session.bind.engine is self.db_slave.engine)

    def test_table_creation(self):
        session = self.db_master_session
        result = session.execute('select * from cell;')
        self.assertTrue(result.first() is None)
        result = session.execute('select * from measure;')
        self.assertTrue(result.first() is None)


class TestCell(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.db import Cell
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
        from ichnaea.db import CellMeasure
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
        from ichnaea.db import Wifi
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
        from ichnaea.db import WifiBlacklist
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
        from ichnaea.db import WifiMeasure
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
        from ichnaea.db import Measure
        return Measure(**kw)

    def test_constructor(self):
        measure = self._make_one()
        self.assertTrue(measure.id is None)

    def test_fields(self):
        measure = self._make_one(
            lat=12345678, lon=23456789, cell="[]", wifi="[]")
        session = self.db_master_session
        session.add(measure)
        session.commit()

        result = session.query(measure.__class__).first()
        self.assertTrue(isinstance(result.created, datetime.datetime))
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.lon, 23456789)
        self.assertEqual(result.cell, "[]")
        self.assertEqual(result.wifi, "[]")


class TestScore(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.db import Score
        return Score(**kw)

    def test_constructor(self):
        score = self._make_one()
        self.assertTrue(score.id is None)

    def test_fields(self):
        score = self._make_one(userid=3, value=15)
        session = self.db_master_session
        session.add(score)
        session.commit()

        result = session.query(score.__class__).first()
        self.assertEqual(result.userid, 3)
        self.assertEqual(result.value, 15)


class TestStat(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.db import Stat
        return Stat(**kw)

    def test_constructor(self):
        stat = self._make_one()
        self.assertTrue(stat.id is None)

    def test_fields(self):
        utcday = datetime.datetime.utcnow().date()
        stat = self._make_one(key=0, time=utcday, value=13)
        session = self.db_master_session
        session.add(stat)
        session.commit()

        result = session.query(stat.__class__).first()
        self.assertEqual(result.key, 0)
        self.assertEqual(result.time, utcday)
        self.assertEqual(result.value, 13)

    def test_property(self):
        stat = self._make_one(key=0, value=13)
        session = self.db_master_session
        session.add(stat)
        session.commit()

        result = session.query(stat.__class__).first()
        self.assertEqual(result.key, 0)
        self.assertEqual(result.name, 'location')

        result.name = ''
        self.assertEqual(result.key, -1)


class TestUser(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.db import User
        return User(**kw)

    def test_constructor(self):
        user = self._make_one()
        self.assertTrue(user.id is None)

    def test_fields(self):
        user = self._make_one(nickname=u"World Traveler")
        session = self.db_master_session
        session.add(user)
        session.commit()

        result = session.query(user.__class__).first()
        self.assertEqual(result.nickname, u"World Traveler")
