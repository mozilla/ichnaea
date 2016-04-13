from datetime import timedelta

from sqlalchemy.exc import SQLAlchemyError

from ichnaea.models import ReportSource
from ichnaea.models.cell import (
    CellArea,
    CellAreaOCID,
    CellShard,
    CellShardOCID,
    CellShardGsm,
    CellShardGsmOCID,
    CellShardWcdma,
    CellShardLte,
    decode_cellarea,
    decode_cellid,
    encode_cellarea,
    encode_cellid,
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
from ichnaea import util


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


class TestCellShard(DBTestCase):

    def test_fields(self):
        now = util.utcnow()
        cellid = encode_cellid(Radio.gsm, GB_MCC, GB_MNC, 123, 2345)
        model = CellShard.shard_model(Radio.gsm)
        self.session.add(model.create(
            cellid=cellid, created=now, modified=now,
            radio=Radio.gsm, mcc=GB_MCC, mnc=GB_MNC, lac=123, cid=2345, psc=1,
            lat=GB_LAT, lon=GB_LON,
            max_lat=GB_LAT + 0.1, min_lat=GB_LAT - 0.1,
            max_lon=GB_LON + 0.1, min_lon=GB_LON - 0.1,
            radius=11, region='GB', samples=15,
            source=ReportSource.gnss, weight=1.5, last_seen=now.date(),
            block_first=now.date(), block_last=now.date(), block_count=1))
        self.session.flush()

        result = (self.session.query(model)
                              .filter(model.cellid == cellid)).first()
        self.assertEqual(result.areaid, cellid[:7])
        self.assertEqual(encode_cellid(*result.cellid), cellid)
        self.assertEqual(result.radio, Radio.gsm)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, GB_MNC)
        self.assertEqual(result.lac, 123)
        self.assertEqual(result.cid, 2345)
        self.assertEqual(result.psc, 1)
        self.assertEqual(result.created, now)
        self.assertEqual(result.modified, now)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.radius, 11)
        self.assertEqual(result.region, 'GB')
        self.assertEqual(result.samples, 15)
        self.assertEqual(result.source, ReportSource.gnss)
        self.assertEqual(result.weight, 1.5)
        self.assertEqual(result.last_seen, now.date())
        self.assertEqual(result.block_first, now.date())
        self.assertEqual(result.block_last, now.date())
        self.assertEqual(result.block_count, 1)

    def test_shard_id(self):
        self.assertEqual(CellShard.shard_id(Radio.lte), 'lte')
        self.assertEqual(CellShard.shard_id(Radio.umts), 'wcdma')
        self.assertEqual(CellShard.shard_id('gsm'), 'gsm')
        self.assertEqual(CellShard.shard_id('umts'), 'wcdma')
        self.assertEqual(CellShard.shard_id(''), None)
        self.assertEqual(CellShard.shard_id(None), None)

        cell_tuple = (Radio.lte, GB_MCC, GB_MNC, 1, 2)
        self.assertEqual(CellShard.shard_id(cell_tuple), 'lte')
        cellid = encode_cellid(*cell_tuple)
        self.assertEqual(CellShard.shard_id(cellid), 'lte')

    def test_shard_model(self):
        self.assertIs(CellShard.shard_model(Radio.gsm), CellShardGsm)
        self.assertIs(CellShard.shard_model(Radio.wcdma), CellShardWcdma)
        self.assertIs(CellShard.shard_model(Radio.lte), CellShardLte)
        self.assertIs(CellShard.shard_model(''), None)
        self.assertIs(CellShard.shard_model(None), None)

        cell_tuple = (Radio.lte, GB_MCC, GB_MNC, 1, 2)
        self.assertEqual(CellShard.shard_model(cell_tuple), CellShardLte)
        cellid = encode_cellid(*cell_tuple)
        self.assertEqual(CellShard.shard_model(cellid), CellShardLte)

    def test_shards(self):
        self.assertEqual(set(CellShard.shards().keys()),
                         set(['gsm', 'wcdma', 'lte']))
        self.assertEqual(set(CellShard.shards().values()),
                         set([CellShardGsm, CellShardWcdma, CellShardLte]))

    def test_init_empty(self):
        self.session.add(CellShardGsm())
        with self.assertRaises(SQLAlchemyError):
            self.session.flush()

    def test_init_fail(self):
        self.session.add(CellShardGsm(cellid='abc'))
        with self.assertRaises(SQLAlchemyError):
            self.session.flush()

    def test_blocked(self):
        today = util.utcnow().date()
        two_weeks = today - timedelta(days=14)
        self.assertFalse(CellShardGsm().blocked())
        self.assertTrue(CellShardGsm(block_count=100).blocked())
        self.assertTrue(CellShardGsm(block_last=today).blocked())
        self.assertFalse(CellShardGsm(block_last=two_weeks).blocked())
        self.assertTrue(CellShardGsm(block_last=two_weeks).blocked(two_weeks))

    def test_score(self):
        now = util.utcnow()
        cell = CellShard.shard_model(Radio.gsm).create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=GB_MNC, lac=2, cid=3,
            created=now, modified=now, radius=10, samples=2)
        self.assertAlmostEqual(cell.score(now), 0.1, 2)


class TestCellShardOCID(DBTestCase):

    def test_areaid(self):
        cellid = encode_cellid(Radio.gsm, GB_MCC, GB_MNC, 123, 2345)
        self.session.add(CellShardOCID.create(
            cellid=cellid,
            radio=Radio.gsm, mcc=GB_MCC, mnc=GB_MNC, lac=123, cid=2345))
        self.session.flush()

        result = self.session.query(CellShardGsmOCID).first()
        self.assertEqual(result.areaid, cellid[:7])

    def test_cellid(self):
        query = (self.session.query(CellShardGsmOCID)
                             .filter(CellShardGsmOCID.cellid == (1, 2)))
        self.assertRaises(Exception, query.first)

    def test_cellid_null(self):
        result = (self.session.query(CellShardGsmOCID)
                              .filter(CellShardGsmOCID.cellid.is_(None))).all()
        self.assertEqual(result, [])

        self.session.add(CellShardGsmOCID(
            cellid=None,
            radio=Radio.gsm, mcc=GB_MCC, mnc=GB_MNC, lac=123, cid=2345))
        with self.assertRaises(Exception):
            self.session.flush()

    def test_region(self):
        cellid = encode_cellid(Radio.gsm, GB_MCC, GB_MNC, 123, 2345)
        self.session.add(CellShardOCID.create(
            cellid=cellid, lat=GB_LAT, lon=GB_LON, region=None,
            radio=Radio.gsm, mcc=GB_MCC, mnc=GB_MNC, lac=123, cid=2345))
        self.session.flush()

        result = self.session.query(CellShardGsmOCID).first()
        self.assertEqual(result.region, 'GB')

    def test_fields(self):
        now = util.utcnow()
        cellid = encode_cellid(Radio.gsm, GB_MCC, GB_MNC, 123, 2345)
        self.session.add(CellShardOCID.create(
            cellid=cellid, created=now, modified=now,
            radio=Radio.gsm, mcc=GB_MCC, mnc=GB_MNC, lac=123, cid=2345, psc=1,
            lat=GB_LAT, lon=GB_LON,
            max_lat=GB_LAT + 0.1, min_lat=GB_LAT - 0.1,
            max_lon=GB_LON + 0.1, min_lon=GB_LON - 0.1,
            radius=11, region='GB', samples=15,
            source=ReportSource.gnss, weight=1.5, last_seen=now.date(),
            block_first=now.date(), block_last=now.date(), block_count=1))
        self.session.flush()

        query = (self.session.query(CellShardGsmOCID)
                             .filter(CellShardGsmOCID.cellid == cellid))
        result = query.first()
        self.assertEqual(result.areaid, cellid[:7])
        self.assertEqual(encode_cellid(*result.cellid), cellid)
        self.assertEqual(result.radio, Radio.gsm)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, GB_MNC)
        self.assertEqual(result.lac, 123)
        self.assertEqual(result.cid, 2345)
        self.assertEqual(result.psc, 1)
        self.assertEqual(result.created, now)
        self.assertEqual(result.modified, now)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.radius, 11)
        self.assertEqual(result.region, 'GB')
        self.assertEqual(result.samples, 15)
        self.assertEqual(result.source, ReportSource.gnss)
        self.assertEqual(result.weight, 1.5)
        self.assertEqual(result.last_seen, now.date())
        self.assertEqual(result.block_first, now.date())
        self.assertEqual(result.block_last, now.date())
        self.assertEqual(result.block_count, 1)

    def test_score(self):
        now = util.utcnow()
        cell = CellShardOCID.create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=GB_MNC, lac=2, cid=3,
            created=now, modified=now, radius=10, samples=2)
        self.assertAlmostEqual(cell.score(now), 0.1, 2)


class TestCellArea(DBTestCase):

    def test_areaid(self):
        areaid = (Radio.gsm, GB_MCC, GB_MNC, 1)
        self.session.add(CellArea(
            areaid=areaid,
            radio=Radio.wcdma, mcc=GB_MCC, mnc=GB_MNC, lac=1234))
        self.session.flush()

        result = self.session.query(CellArea).first()
        self.assertEqual(result.areaid, (Radio.gsm, GB_MCC, GB_MNC, 1))

        result = (self.session.query(CellArea)
                              .filter(CellArea.areaid == areaid)).first()
        self.assertEqual(result.areaid, (Radio.gsm, GB_MCC, GB_MNC, 1))

        query = self.session.query(CellArea).filter(CellArea.areaid == (1, 2))
        self.assertRaises(Exception, query.first)

    def test_areaid_bytes(self):
        areaid = encode_cellarea(Radio.gsm, GB_MCC, GB_MNC, 1)
        self.session.add(CellArea(
            areaid=areaid,
            radio=Radio.wcdma, mcc=GB_MCC, mnc=GB_MNC, lac=1234))
        self.session.flush()

        result = self.session.query(CellArea).first()
        self.assertEqual(result.areaid, (Radio.gsm, GB_MCC, GB_MNC, 1))

        result = (self.session.query(CellArea)
                              .filter(CellArea.areaid == areaid)).first()
        self.assertEqual(result.areaid, (Radio.gsm, GB_MCC, GB_MNC, 1))

    def test_areaid_null(self):
        result = (self.session.query(CellArea)
                              .filter(CellArea.areaid.is_(None))).all()
        self.assertEqual(result, [])

        self.session.add(CellArea(
            areaid=None,
            radio=Radio.wcdma, mcc=GB_MCC, mnc=GB_MNC, lac=1234))
        with self.assertRaises(Exception):
            self.session.flush()

    def test_areaid_derived(self):
        self.session.add(CellArea.create(
            radio=Radio.wcdma, mcc=GB_MCC, mnc=GB_MNC, lac=1234))
        self.session.flush()

        result = self.session.query(CellArea).first()
        self.assertEqual(result.areaid, (Radio.wcdma, GB_MCC, GB_MNC, 1234))

    def test_areaid_explicit(self):
        self.session.add(CellArea.create(
            areaid=(Radio.gsm, GB_MCC, GB_MNC, 1),
            radio=Radio.wcdma, mcc=GB_MCC, mnc=GB_MNC, lac=1234))
        self.session.flush()

        result = self.session.query(CellArea).first()
        self.assertEqual(result.areaid, (Radio.wcdma, GB_MCC, GB_MNC, 1234))

    def test_areaid_unhex(self):
        value = '''\
unhex(concat(
lpad(hex({radio}), 2, 0),
lpad(hex({mcc}), 4, 0),
lpad(hex({mnc}), 4, 0),
lpad(hex({lac}), 4, 0))),
{radio}, {mcc}, {mnc}, {lac}
'''.format(radio=int(Radio.gsm), mcc=310, mnc=1, lac=65534)
        stmt = ('insert into cell_area '
                '(areaid, radio, mcc, mnc, lac) '
                'values (%s)') % value
        self.session.execute(stmt)
        self.session.flush()
        cell = self.session.query(CellArea).one()
        self.assertEqual(cell.areaid, (Radio.gsm, 310, 1, 65534))

    def test_areaid_hex(self):
        value = '''\
cast(conv(substr(hex(`areaid`), 1, 2), 16, 10) as unsigned),
cast(conv(substr(hex(`areaid`), 3, 4), 16, 10) as unsigned),
cast(conv(substr(hex(`areaid`), 7, 4), 16, 10) as unsigned),
cast(conv(substr(hex(`areaid`), 11, 4), 16, 10) as unsigned)
'''
        self.session.add(CellArea(
            areaid=(Radio.gsm, 310, 1, 65534),
            radio=Radio.gsm, mcc=310, mnc=1, lac=65534))
        self.session.flush()
        stmt = 'select %s from cell_area' % value
        row = self.session.execute(stmt).fetchone()
        self.assertEqual(row, (0, 310, 1, 65534))

    def test_invalid(self):
        self.assertEqual(CellArea.validate({'radio': 'invalid'}), None)

    def test_fields(self):
        self.session.add(CellArea.create(
            areaid=(Radio.wcdma, GB_MCC, GB_MNC, 1234),
            radio=Radio.wcdma, mcc=GB_MCC, mnc=GB_MNC, lac=1234,
            lat=GB_LAT, lon=GB_LON, region='GB',
            radius=10, avg_cell_radius=10, num_cells=15))
        self.session.flush()

        result = self.session.query(CellArea).first()
        self.assertEqual(result.areaid, (Radio.wcdma, GB_MCC, GB_MNC, 1234)),
        self.assertEqual(result.radio, Radio.wcdma)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, GB_MNC)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.radius, 10)
        self.assertEqual(result.region, 'GB')
        self.assertEqual(result.avg_cell_radius, 10)
        self.assertEqual(result.num_cells, 15)

    def test_score(self):
        now = util.utcnow()
        area = CellArea.create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=GB_MNC, lac=2,
            created=now, modified=now, radius=10, num_cells=4)
        self.assertAlmostEqual(area.score(now), 0.2, 2)
        area = CellArea.create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=GB_MNC, lac=2,
            created=now, modified=now, radius=0, num_cells=100)
        self.assertAlmostEqual(area.score(now), 0.1, 2)


class TestCellAreaOCID(DBTestCase):

    def test_region(self):
        areaid = encode_cellarea(Radio.gsm, GB_MCC, GB_MNC, 123)
        self.session.add(CellAreaOCID.create(
            areaid=areaid, lat=GB_LAT, lon=GB_LON, region=None,
            radio=Radio.gsm, mcc=GB_MCC, mnc=GB_MNC, lac=123))
        self.session.flush()

        result = self.session.query(CellAreaOCID).first()
        self.assertEqual(result.region, 'GB')

    def test_fields(self):
        areaid = encode_cellarea(Radio.wcdma, GB_MCC, GB_MNC, 123)
        self.session.add(CellAreaOCID.create(
            areaid=areaid, radio=Radio.wcdma, mcc=GB_MCC, mnc=GB_MNC, lac=123,
            lat=GB_LAT, lon=GB_LON, radius=10, region='GB',
            avg_cell_radius=11, num_cells=15))
        self.session.flush()

        result = self.session.query(CellAreaOCID).first()
        self.assertEqual(encode_cellarea(*result.areaid), areaid)
        self.assertEqual(result.radio, Radio.wcdma)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, GB_MNC)
        self.assertEqual(result.lac, 123)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.radius, 10)
        self.assertEqual(result.region, 'GB')
        self.assertEqual(result.avg_cell_radius, 11)
        self.assertEqual(result.num_cells, 15)

    def test_score(self):
        now = util.utcnow()
        area = CellAreaOCID.create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=GB_MNC, lac=2,
            created=now, modified=now, radius=10, num_cells=4)
        self.assertAlmostEqual(area.score(now), 0.2, 2)
        area = CellAreaOCID.create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=GB_MNC, lac=2,
            created=now, modified=now, radius=0, num_cells=100)
        self.assertAlmostEqual(area.score(now), 0.1, 2)
