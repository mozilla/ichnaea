from ichnaea.models.cell import (
    Cell,
    CellArea,
    CellBlocklist,
    decode_cellarea,
    decode_cellid,
    encode_cellarea,
    encode_cellid,
    OCIDCell,
    OCIDCellArea,
    Radio,
)
from ichnaea.tests.base import (
    TestCase,
    DBTestCase,
    GB_LAT,
    GB_LON,
    GB_MCC,
    GB_MNC,
)


class TestCellCodec(TestCase):

    def test_decode_area(self):
        value = decode_cellarea(b'\x00\x016\x00\x01\x00\x00')
        self.assertEqual(value, (Radio.gsm, 310, 1, 0))
        self.assertEqual(type(value[0]), Radio)

        value = decode_cellarea(b'\x02\x016\x00\x01\x00\x0c')
        self.assertEqual(value, (Radio.wcdma, 310, 1, 12))
        self.assertEqual(type(value[0]), Radio)

    def test_decode_cell(self):
        value = decode_cellid(b'\x00\x016\x00\x00\x00\x01\x00\x00\x00\x01')
        self.assertEqual(value, (Radio.gsm, 310, 0, 1, 1))
        self.assertEqual(type(value[0]), Radio)

        value = decode_cellid(b'\x02\x016\x00\x01\x00\x0c\x00\x00\x00\x00')
        self.assertEqual(value, (Radio.wcdma, 310, 1, 12, 0))
        self.assertEqual(type(value[0]), Radio)

    def test_encode_area(self):
        value = encode_cellarea(Radio.gsm, 310, 1, 0)
        self.assertEqual(len(value), 7)
        self.assertEqual(value, b'\x00\x016\x00\x01\x00\x00')

        value = encode_cellarea(Radio.wcdma, 310, 1, 12)
        self.assertEqual(len(value), 7)
        self.assertEqual(value, b'\x02\x016\x00\x01\x00\x0c')

    def test_encode_cell(self):
        value = encode_cellid(Radio.gsm, 310, 0, 1, 1)
        self.assertEqual(len(value), 11)
        self.assertEqual(value, b'\x00\x016\x00\x00\x00\x01\x00\x00\x00\x01')

        value = encode_cellid(Radio.wcdma, 310, 1, 12, 0)
        self.assertEqual(len(value), 11)
        self.assertEqual(value, b'\x02\x016\x00\x01\x00\x0c\x00\x00\x00\x00')

    def test_max(self):
        bit16 = 2 ** 16 - 1
        bit32 = 2 ** 32 - 1

        value = encode_cellarea(
            Radio.wcdma, bit16, bit16, bit16, codec='base64')
        self.assertEqual(value, b'Av///////w==')

        value = encode_cellid(
            Radio.wcdma, bit16, bit16, bit16, bit32, codec='base64')
        self.assertEqual(value, b'Av////////////8=')

        value = decode_cellarea(b'Av///////w==', codec='base64')
        self.assertEqual(value, (Radio.wcdma, bit16, bit16, bit16))
        self.assertEqual(type(value[0]), Radio)

        value = decode_cellid(b'Av////////////8=', codec='base64')
        self.assertEqual(value, (Radio.wcdma, bit16, bit16, bit16, bit32))
        self.assertEqual(type(value[0]), Radio)

    def test_min(self):
        value = encode_cellarea(Radio.gsm, 0, 0, 0, codec='base64')
        self.assertEqual(value, b'AAAAAAAAAA==')

        value = encode_cellid(Radio.gsm, 0, 0, 0, 0, codec='base64')
        self.assertEqual(value, b'AAAAAAAAAAAAAAA=')

        value = decode_cellarea(b'AAAAAAAAAA==', codec='base64')
        self.assertEqual(value, (Radio.gsm, 0, 0, 0))
        self.assertEqual(type(value[0]), Radio)

        value = decode_cellid(b'AAAAAAAAAAAAAAA=', codec='base64')
        self.assertEqual(value, (Radio.gsm, 0, 0, 0, 0))
        self.assertEqual(type(value[0]), Radio)


class TestCell(DBTestCase):

    def test_fields(self):
        session = self.session
        session.add(Cell.create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=GB_MNC, lac=1234, cid=23456,
            lat=GB_LAT, lon=GB_LON, total_measures=15))
        session.flush()

        result = session.query(Cell).first()
        self.assertEqual(result.radio, Radio.gsm)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, GB_MNC)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.cid, 23456)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.total_measures, 15)


class TestCellArea(DBTestCase):

    def test_fields(self):
        session = self.session
        session.add(CellArea.create(
            radio=Radio.wcdma, mcc=GB_MCC, mnc=GB_MNC, lac=1234, range=10,
            lat=GB_LAT, lon=GB_LON, avg_cell_range=10, num_cells=15))
        session.flush()

        result = session.query(CellArea).first()
        self.assertEqual(result.radio, Radio.wcdma)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, GB_MNC)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.range, 10)
        self.assertEqual(result.avg_cell_range, 10)
        self.assertEqual(result.num_cells, 15)


class TestCellBlocklist(DBTestCase):

    def test_fields(self):
        session = self.session
        session.add(CellBlocklist(
            radio=Radio.lte, mcc=GB_MCC, mnc=GB_MNC,
            lac=1234, cid=23456, count=2))
        session.flush()

        result = session.query(CellBlocklist).first()
        self.assertEqual(result.radio, Radio.lte)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, GB_MNC)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.cid, 23456)
        self.assertEqual(result.count, 2)


class TestOCIDCell(DBTestCase):

    def test_fields(self):
        session = self.session
        session.add(OCIDCell.create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=GB_MNC, lac=1234, cid=23456,
            lat=GB_LAT, lon=GB_LON, range=1000, total_measures=15))
        session.flush()

        result = session.query(OCIDCell).first()
        self.assertEqual(result.radio, Radio.gsm)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, GB_MNC)
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
        session.add(OCIDCellArea.create(
            radio=Radio.umts, mcc=GB_MCC, mnc=GB_MNC, lac=1234, range=10,
            lat=GB_LAT, lon=GB_LON, avg_cell_range=10, num_cells=15))
        session.flush()

        result = session.query(OCIDCellArea).first()
        self.assertEqual(result.radio, Radio.umts)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, GB_MNC)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.range, 10)
        self.assertEqual(result.avg_cell_range, 10)
        self.assertEqual(result.num_cells, 15)
