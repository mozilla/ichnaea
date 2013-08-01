from ichnaea.tests.base import DBTestCase


class TestDatabase(DBTestCase):

    def test_constructor(self):
        self.assertEqual(self.db.engine.name, 'sqlite')

    def test_session(self):
        self.assertTrue(self.db_session.bind is self.db.engine)

    def test_table_creation(self):
        session = self.db_session
        result = session.execute('select * from cell;')
        self.assertTrue(result.first() is None)
        result = session.execute('select * from measure;')
        self.assertTrue(result.first() is None)


class TestCell(DBTestCase):

    def _make_one(self):
        from ichnaea.db import Cell
        return Cell()

    def test_constructor(self):
        cell = self._make_one()
        self.assertTrue(cell.id is None)

    def test_fields(self):
        cell = self._make_one()
        cell.lat = 12345678
        cell.lon = 23456789
        cell.mcc = 100
        cell.mnc = 5
        cell.lac = 12345
        cell.cid = 234567

        session = self.db_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.cid, 234567)


class TestCellMeasure(DBTestCase):

    def _make_one(self):
        from ichnaea.db import CellMeasure
        return CellMeasure()

    def test_constructor(self):
        cell = self._make_one()
        self.assertTrue(cell.id is None)

    def test_fields(self):
        cell = self._make_one()
        cell.lat = 12345678
        cell.lon = 23456789
        cell.radio = 0
        cell.mcc = 100
        cell.mnc = 5
        cell.lac = 12345
        cell.cid = 234567
        cell.asu = 26
        cell.signal = -61
        cell.ta = 10

        session = self.db_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.id, 1)
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

    def _make_one(self):
        from ichnaea.db import Wifi
        return Wifi()

    def test_constructor(self):
        wifi = self._make_one()
        self.assertTrue(wifi.key is None)

    def test_fields(self):
        wifi = self._make_one()
        key = "3680873e9b83738eb72946d19e971e023e51fd01"
        wifi.key = key
        wifi.lat = 12345678
        wifi.lon = 23456789
        wifi.range = 200

        session = self.db_session
        session.add(wifi)
        session.commit()

        result = session.query(wifi.__class__).first()
        self.assertEqual(result.key, key)
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.lon, 23456789)
        self.assertEqual(result.range, 200)


class TestWifiMeasure(DBTestCase):

    def _make_one(self):
        from ichnaea.db import WifiMeasure
        return WifiMeasure()

    def test_constructor(self):
        wifi = self._make_one()
        self.assertTrue(wifi.id is None)

    def test_fields(self):
        wifi = self._make_one()
        key = "3680873e9b83738eb72946d19e971e023e51fd01"
        wifi.lat = 12345678
        wifi.lon = 23456789
        wifi.key = key
        wifi.channel = 2412
        wifi.signal = -45

        session = self.db_session
        session.add(wifi)
        session.commit()

        result = session.query(wifi.__class__).first()
        self.assertEqual(result.id, 1)
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.lon, 23456789)
        self.assertEqual(result.key, key)
        self.assertEqual(result.channel, 2412)
        self.assertEqual(result.signal, -45)


class TestMeasure(DBTestCase):

    def _make_one(self):
        from ichnaea.db import Measure
        return Measure()

    def test_constructor(self):
        measure = self._make_one()
        self.assertTrue(measure.id is None)

    def test_fields(self):
        measure = self._make_one()
        measure.lat = 12345678
        measure.lon = 23456789
        measure.cell = "[]"
        measure.wifi = "[]"

        session = self.db_session
        session.add(measure)
        session.commit()

        result = session.query(measure.__class__).first()
        self.assertEqual(result.id, 1)
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.lon, 23456789)
        self.assertEqual(result.cell, "[]")
        self.assertEqual(result.wifi, "[]")


class TestScore(DBTestCase):

    def _make_one(self):
        from ichnaea.db import Score
        return Score()

    def test_constructor(self):
        score = self._make_one()
        self.assertTrue(score.id is None)

    def test_fields(self):
        score = self._make_one()
        score.userid = 3
        score.value = 15

        session = self.db_session
        session.add(score)
        session.commit()

        result = session.query(score.__class__).first()
        self.assertEqual(result.id, 1)
        self.assertEqual(result.userid, 3)
        self.assertEqual(result.value, 15)


class TestUser(DBTestCase):

    def _make_one(self):
        from ichnaea.db import User
        return User()

    def test_constructor(self):
        user = self._make_one()
        self.assertTrue(user.id is None)

    def test_fields(self):
        user = self._make_one()
        user.token = "898fccec2262417ca49d2814ac61e2c3"
        user.nickname = "World Traveler"

        session = self.db_session
        session.add(user)
        session.commit()

        result = session.query(user.__class__).first()
        self.assertEqual(result.id, 1)
        self.assertEqual(result.token, "898fccec2262417ca49d2814ac61e2c3")
        self.assertEqual(result.nickname, "World Traveler")
