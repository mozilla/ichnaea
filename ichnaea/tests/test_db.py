from unittest import TestCase


class TestDatabase(TestCase):

    def _make_one(self):
        from ichnaea.db import Database
        return Database('sqlite://')

    def test_constructor(self):
        db = self._make_one()
        self.assertEqual(db.engine.name, 'sqlite')

    def test_session(self):
        db = self._make_one()
        session = db.session()
        self.assertTrue(session.bind is db.engine)

    def test_table_creation(self):
        db = self._make_one()
        session = db.session()
        result = session.execute('select * from cell;')
        self.assertTrue(result.first() is None)
        result = session.execute('select * from measure;')
        self.assertTrue(result.first() is None)


class TestCell(TestCase):

    def _make_one(self):
        from ichnaea.db import Cell
        return Cell()

    def _get_session(self):
        from ichnaea.db import Database
        return Database('sqlite://').session()

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

        session = self._get_session()
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.cid, 234567)


class TestCellMeasure(TestCase):

    def _make_one(self):
        from ichnaea.db import CellMeasure
        return CellMeasure()

    def _get_session(self):
        from ichnaea.db import Database
        return Database('sqlite://').session()

    def test_constructor(self):
        cell = self._make_one()
        self.assertTrue(cell.id is None)

    def test_fields(self):
        cell = self._make_one()

        session = self._get_session()
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.id, 1)


class TestWifi(TestCase):

    def _make_one(self):
        from ichnaea.db import Wifi
        return Wifi()

    def _get_session(self):
        from ichnaea.db import Database
        return Database('sqlite://').session()

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

        session = self._get_session()
        session.add(wifi)
        session.commit()

        result = session.query(wifi.__class__).first()
        self.assertEqual(result.key, key)
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.lon, 23456789)
        self.assertEqual(result.range, 200)


class TestWifiMeasure(TestCase):

    def _make_one(self):
        from ichnaea.db import WifiMeasure
        return WifiMeasure()

    def _get_session(self):
        from ichnaea.db import Database
        return Database('sqlite://').session()

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

        session = self._get_session()
        session.add(wifi)
        session.commit()

        result = session.query(wifi.__class__).first()
        self.assertEqual(result.id, 1)
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.lon, 23456789)
        self.assertEqual(result.key, key)
        self.assertEqual(result.channel, 2412)
        self.assertEqual(result.signal, -45)


class TestMeasure(TestCase):

    def _make_one(self):
        from ichnaea.db import Measure
        return Measure()

    def _get_session(self):
        from ichnaea.db import Database
        return Database('sqlite://').session()

    def test_constructor(self):
        measure = self._make_one()
        self.assertTrue(measure.id is None)

    def test_fields(self):
        measure = self._make_one()
        measure.lat = 12345678
        measure.lon = 23456789
        measure.cell = "[]"
        measure.wifi = "[]"

        session = self._get_session()
        session.add(measure)
        session.commit()

        result = session.query(measure.__class__).first()
        self.assertEqual(result.id, 1)
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.lon, 23456789)
        self.assertEqual(result.cell, "[]")
        self.assertEqual(result.wifi, "[]")


class TestScore(TestCase):

    def _make_one(self):
        from ichnaea.db import Score
        return Score()

    def _get_session(self):
        from ichnaea.db import Database
        return Database('sqlite://').session()

    def test_constructor(self):
        score = self._make_one()
        self.assertTrue(score.id is None)

    def test_fields(self):
        score = self._make_one()
        score.userid = 3
        score.value = 15

        session = self._get_session()
        session.add(score)
        session.commit()

        result = session.query(score.__class__).first()
        self.assertEqual(result.id, 1)
        self.assertEqual(result.userid, 3)
        self.assertEqual(result.value, 15)


class TestUser(TestCase):

    def _make_one(self):
        from ichnaea.db import User
        return User()

    def _get_session(self):
        from ichnaea.db import Database
        return Database('sqlite://').session()

    def test_constructor(self):
        user = self._make_one()
        self.assertTrue(user.id is None)

    def test_fields(self):
        user = self._make_one()
        user.token = "898fccec2262417ca49d2814ac61e2c3"
        user.nickname = "World Traveler"

        session = self._get_session()
        session.add(user)
        session.commit()

        result = session.query(user.__class__).first()
        self.assertEqual(result.id, 1)
        self.assertEqual(result.token, "898fccec2262417ca49d2814ac61e2c3")
        self.assertEqual(result.nickname, "World Traveler")
