from ichnaea.models import RADIO_TYPE
from ichnaea.tests.base import DBTestCase


class TestCell(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import Cell
        return Cell(**kw)

    def test_constructor(self):
        cell = self._make_one()
        self.assertEqual(cell.new_measures, 0)
        self.assertEqual(cell.total_measures, 0)

    def test_fields(self):
        cell = self._make_one(
            radio=1, lat=1.2345678, lon=2.3456789, mcc=100, mnc=5,
            lac=1234, cid=23456, new_measures=2, total_measures=15)
        session = self.db_master_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.lat, 1.2345678)
        self.assertEqual(result.lon, 2.3456789)
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.cid, 23456)
        self.assertEqual(result.new_measures, 2)
        self.assertEqual(result.total_measures, 15)


class TestCellArea(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import CellArea
        return CellArea(**kw)

    def test_constructor(self):
        cell = self._make_one()
        self.assertEqual(cell.range, 0)
        self.assertEqual(cell.avg_cell_range, 0)
        self.assertEqual(cell.num_cells, 0)

    def test_fields(self):
        cell = self._make_one(
            range=10,
            avg_cell_range=10,
            radio=1,
            lac=1234,
            lat=1.2345678,
            lon=2.3456789,
            mcc=100,
            mnc=5,
            num_cells=15,
        )
        session = self.db_master_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.range, 10)
        self.assertEqual(result.avg_cell_range, 10)
        self.assertEqual(result.radio, 1)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.lat, 1.2345678)
        self.assertEqual(result.lon, 2.3456789)
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.num_cells, 15)


class TestOCIDCell(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import OCIDCell
        return OCIDCell(**kw)

    def test_constructor(self):
        cell = self._make_one()
        self.assertEqual(cell.total_measures, 0)

    def test_fields(self):
        cell = self._make_one(
            radio=RADIO_TYPE['gsm'], mcc=100, mnc=5, lac=1234, cid=23456,
            lat=1.2345678, lon=2.3456789, range=1000, total_measures=15,
        )
        session = self.db_master_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.radio, RADIO_TYPE['gsm'])
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.cid, 23456)
        self.assertEqual(result.lat, 1.2345678)
        self.assertEqual(result.lon, 2.3456789)
        self.assertEqual(result.total_measures, 15)
        self.assertEqual(result.min_lat, 1.225567790999991)
        self.assertEqual(result.min_lon, 2.3184002892204245)
        self.assertEqual(result.max_lat, 1.243567809000009)
        self.assertEqual(result.max_lon, 2.372957510779575)


class TestOCIDCellArea(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import OCIDCellArea
        return OCIDCellArea(**kw)

    def test_constructor(self):
        cell = self._make_one()
        self.assertEqual(cell.range, 0)
        self.assertEqual(cell.avg_cell_range, 0)
        self.assertEqual(cell.num_cells, 0)

    def test_fields(self):
        cell = self._make_one(
            range=10,
            avg_cell_range=10,
            radio=1,
            lac=1234,
            lat=1.2345678,
            lon=2.3456789,
            mcc=100,
            mnc=5,
            num_cells=15,
        )
        session = self.db_master_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.range, 10)
        self.assertEqual(result.avg_cell_range, 10)
        self.assertEqual(result.radio, 1)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.lat, 1.2345678)
        self.assertEqual(result.lon, 2.3456789)
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.num_cells, 15)
