from ichnaea.models.cell import (
    Cell,
    CellArea,
    CellBlacklist,
    OCIDCell,
    OCIDCellArea,
    Radio,
)
from ichnaea.tests.base import (
    DBTestCase,
    GB_LAT,
    GB_LON,
    GB_MCC,
)


class TestCell(DBTestCase):

    def test_fields(self):
        session = self.session
        session.add(Cell.create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=5, lac=1234, cid=23456,
            lat=GB_LAT, lon=GB_LON, total_measures=15))
        session.flush()

        result = session.query(Cell).first()
        self.assertEqual(result.radio, Radio.gsm)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.cid, 23456)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.total_measures, 15)


class TestCellArea(DBTestCase):

    def test_fields(self):
        session = self.session
        session.add(CellArea(
            radio=Radio.cdma, mcc=GB_MCC, mnc=5, lac=1234, range=10,
            lat=GB_LAT, lon=GB_LON, avg_cell_range=10, num_cells=15))
        session.flush()

        result = session.query(CellArea).first()
        self.assertEqual(result.radio, Radio.cdma)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.range, 10)
        self.assertEqual(result.avg_cell_range, 10)
        self.assertEqual(result.num_cells, 15)


class TestCellBlacklist(DBTestCase):

    def test_fields(self):
        session = self.session
        session.add(CellBlacklist(
            radio=Radio.lte, mcc=GB_MCC, mnc=5, lac=1234, cid=23456, count=2))
        session.flush()

        result = session.query(CellBlacklist).first()
        self.assertEqual(result.radio, Radio.lte)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.cid, 23456)
        self.assertEqual(result.count, 2)


class TestOCIDCell(DBTestCase):

    def test_fields(self):
        session = self.session
        session.add(OCIDCell.create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=5, lac=1234, cid=23456,
            lat=GB_LAT, lon=GB_LON, range=1000, total_measures=15))
        session.flush()

        result = session.query(OCIDCell).first()
        self.assertEqual(result.radio, Radio.gsm)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.cid, 23456)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.total_measures, 15)
        self.assertAlmostEqual(result.min_lat, GB_LAT - 0.009, 7)
        self.assertAlmostEqual(result.min_lon, GB_LON - 0.02727469, 7)
        self.assertAlmostEqual(result.max_lat, GB_LAT + 0.009, 7)
        self.assertAlmostEqual(result.max_lon, GB_LON + 0.02727469, 7)


class TestOCIDCellArea(DBTestCase):

    def test_fields(self):
        session = self.session
        session.add(OCIDCellArea(
            radio=Radio.umts, mcc=GB_MCC, mnc=5, lac=1234, range=10,
            lat=GB_LAT, lon=GB_LON, avg_cell_range=10, num_cells=15))
        session.flush()

        result = session.query(OCIDCellArea).first()
        self.assertEqual(result.radio, Radio.umts)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.range, 10)
        self.assertEqual(result.avg_cell_range, 10)
        self.assertEqual(result.num_cells, 15)
