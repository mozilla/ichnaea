from ichnaea.models.cell import (
    Cell,
    CellArea,
    CellBlacklist,
    OCIDCell,
    OCIDCellArea,
    RADIO_TYPE,
)
from ichnaea.tests.base import DBTestCase


class TestCell(DBTestCase):

    def test_fields(self):
        cell = Cell(
            radio=RADIO_TYPE['gsm'], mcc=100, mnc=5, lac=1234, cid=23456,
            lat=1.2345678, lon=2.3456789, new_measures=2, total_measures=15)
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
        self.assertEqual(result.new_measures, 2)
        self.assertEqual(result.total_measures, 15)


class TestCellArea(DBTestCase):

    def test_fields(self):
        cell = CellArea(
            radio=RADIO_TYPE['cdma'], lac=1234, mcc=100, mnc=5,
            lat=1.2345678, lon=2.3456789,
            range=10, avg_cell_range=10, num_cells=15,
        )
        session = self.db_master_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.radio, RADIO_TYPE['cdma'])
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.lat, 1.2345678)
        self.assertEqual(result.lon, 2.3456789)
        self.assertEqual(result.range, 10)
        self.assertEqual(result.avg_cell_range, 10)
        self.assertEqual(result.num_cells, 15)


class TestCellBlacklist(DBTestCase):

    def test_fields(self):
        cell = CellBlacklist(
            radio=RADIO_TYPE['lte'], mcc=100, mnc=5, lac=1234, cid=23456,
            count=2)
        session = self.db_master_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.radio, RADIO_TYPE['lte'])
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.cid, 23456)
        self.assertEqual(result.count, 2)


class TestOCIDCell(DBTestCase):

    def test_fields(self):
        cell = OCIDCell(
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

    def test_fields(self):
        cell = OCIDCellArea(
            radio=RADIO_TYPE['umts'], lac=1234, mcc=100, mnc=5,
            lat=1.2345678, lon=2.3456789,
            range=10, avg_cell_range=10, num_cells=15,
        )
        session = self.db_master_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.radio, RADIO_TYPE['umts'])
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.lat, 1.2345678)
        self.assertEqual(result.lon, 2.3456789)
        self.assertEqual(result.range, 10)
        self.assertEqual(result.avg_cell_range, 10)
        self.assertEqual(result.num_cells, 15)
