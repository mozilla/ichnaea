from unittest import TestCase


class TestDB(TestCase):

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
