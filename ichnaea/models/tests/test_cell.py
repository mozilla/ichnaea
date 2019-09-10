from datetime import timedelta
import warnings

import pytest
from sqlalchemy.exc import SAWarning, SQLAlchemyError

from ichnaea.conftest import GB_LAT, GB_LON, GB_MCC, GB_MNC
from ichnaea.models import ReportSource, station_blocked
from ichnaea.models.cell import (
    area_id,
    CellArea,
    CellShard,
    CellShardGsm,
    CellShardWcdma,
    CellShardLte,
    decode_cellarea,
    decode_cellid,
    encode_cellarea,
    encode_cellid,
    Radio,
)

from ichnaea import util


class TestCellCodec(object):
    def test_decode_area(self):
        value = decode_cellarea(b"\x00\x016\x00\x01\x00\x00")
        assert value == (Radio.gsm, 310, 1, 0)
        assert type(value[0]) is Radio

        value = decode_cellarea(b"\x02\x016\x00\x01\x00\x0c")
        assert value == (Radio.wcdma, 310, 1, 12)
        assert type(value[0]) is Radio

    def test_decode_cell(self):
        value = decode_cellid(b"\x00\x016\x00\x00\x00\x01\x00\x00\x00\x01")
        assert value == (Radio.gsm, 310, 0, 1, 1)
        assert type(value[0]) is Radio

        value = decode_cellid(b"\x02\x016\x00\x01\x00\x0c\x00\x00\x00\x00")
        assert value == (Radio.wcdma, 310, 1, 12, 0)
        assert type(value[0]) is Radio

    def test_encode_area(self):
        value = encode_cellarea(Radio.gsm, 310, 1, 0)
        assert len(value) == 7
        assert value == b"\x00\x016\x00\x01\x00\x00"

        value = encode_cellarea(Radio.wcdma, 310, 1, 12)
        assert len(value) == 7
        assert value == b"\x02\x016\x00\x01\x00\x0c"

    def test_encode_cell(self):
        value = encode_cellid(Radio.gsm, 310, 0, 1, 1)
        assert len(value) == 11
        assert value == b"\x00\x016\x00\x00\x00\x01\x00\x00\x00\x01"

        value = encode_cellid(Radio.wcdma, 310, 1, 12, 0)
        assert len(value) == 11
        assert value == b"\x02\x016\x00\x01\x00\x0c\x00\x00\x00\x00"

    def test_max(self):
        bit16 = 2 ** 16 - 1
        bit32 = 2 ** 32 - 1

        value = encode_cellarea(Radio.wcdma, bit16, bit16, bit16, codec="base64")
        assert value == b"Av///////w=="

        value = encode_cellid(Radio.wcdma, bit16, bit16, bit16, bit32, codec="base64")
        assert value == b"Av////////////8="

        value = decode_cellarea(b"Av///////w==", codec="base64")
        assert value == (Radio.wcdma, bit16, bit16, bit16)
        assert type(value[0]) is Radio

        value = decode_cellid(b"Av////////////8=", codec="base64")
        assert value == (Radio.wcdma, bit16, bit16, bit16, bit32)
        assert type(value[0]) is Radio

    def test_min(self):
        value = encode_cellarea(Radio.gsm, 0, 0, 0, codec="base64")
        assert value == b"AAAAAAAAAA=="

        value = encode_cellid(Radio.gsm, 0, 0, 0, 0, codec="base64")
        assert value == b"AAAAAAAAAAAAAAA="

        value = decode_cellarea(b"AAAAAAAAAA==", codec="base64")
        assert value == (Radio.gsm, 0, 0, 0)
        assert type(value[0]) is Radio

        value = decode_cellid(b"AAAAAAAAAAAAAAA=", codec="base64")
        assert value == (Radio.gsm, 0, 0, 0, 0)
        assert type(value[0]) is Radio


class TestCellShard(object):
    def test_fields(self, session):
        now = util.utcnow()
        cellid = encode_cellid(Radio.gsm, GB_MCC, GB_MNC, 123, 2345)
        model = CellShard.shard_model(Radio.gsm)
        session.add(
            model.create(
                cellid=cellid,
                created=now,
                modified=now,
                radio=Radio.gsm,
                mcc=GB_MCC,
                mnc=GB_MNC,
                lac=123,
                cid=2345,
                psc=1,
                lat=GB_LAT,
                lon=GB_LON,
                max_lat=GB_LAT + 0.1,
                min_lat=GB_LAT - 0.1,
                max_lon=GB_LON + 0.1,
                min_lon=GB_LON - 0.1,
                radius=11,
                region="GB",
                samples=15,
                source=ReportSource.gnss,
                weight=1.5,
                last_seen=now.date(),
                block_first=now.date(),
                block_last=now.date(),
                block_count=1,
            )
        )
        session.flush()

        result = (session.query(model).filter(model.cellid == cellid)).first()
        assert area_id(result) == cellid[:7]
        assert encode_cellid(*result.cellid) == cellid
        assert result.radio == Radio.gsm
        assert result.mcc == GB_MCC
        assert result.mnc == GB_MNC
        assert result.lac == 123
        assert result.cid == 2345
        assert result.psc == 1
        assert result.created == now
        assert result.modified == now
        assert result.lat == GB_LAT
        assert result.lon == GB_LON
        assert result.radius == 11
        assert result.region == "GB"
        assert result.samples == 15
        assert result.source == ReportSource.gnss
        assert result.weight == 1.5
        assert result.last_seen == now.date()
        assert result.block_first == now.date()
        assert result.block_last == now.date()
        assert result.block_count == 1

    def test_shard_id(self):
        assert CellShard.shard_id(Radio.lte) == "lte"
        assert CellShard.shard_id(Radio.umts) == "wcdma"
        assert CellShard.shard_id("gsm") == "gsm"
        assert CellShard.shard_id("umts") == "wcdma"
        assert CellShard.shard_id("") is None
        assert CellShard.shard_id(None) is None

        cell_tuple = (Radio.lte, GB_MCC, GB_MNC, 1, 2)
        assert CellShard.shard_id(cell_tuple) == "lte"
        cellid = encode_cellid(*cell_tuple)
        assert CellShard.shard_id(cellid) == "lte"

    def test_shard_model(self):
        assert CellShard.shard_model(Radio.gsm) is CellShardGsm
        assert CellShard.shard_model(Radio.wcdma) is CellShardWcdma
        assert CellShard.shard_model(Radio.lte) is CellShardLte
        assert CellShard.shard_model("") is None
        assert CellShard.shard_model(None) is None

        cell_tuple = (Radio.lte, GB_MCC, GB_MNC, 1, 2)
        assert CellShard.shard_model(cell_tuple) is CellShardLte
        cellid = encode_cellid(*cell_tuple)
        assert CellShard.shard_model(cellid) is CellShardLte

    def test_shards(self):
        assert set(CellShard.shards().keys()) == set(["gsm", "wcdma", "lte"])
        assert set(CellShard.shards().values()) == set(
            [CellShardGsm, CellShardWcdma, CellShardLte]
        )

    def test_init_empty(self, session):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SAWarning)
            session.add(CellShardGsm())
            with pytest.raises(SQLAlchemyError):
                session.flush()

    def test_init_fail(self, session):
        session.add(CellShardGsm(cellid="abc"))
        with pytest.raises(SQLAlchemyError):
            session.flush()

    def test_cellid_null(self, session):
        result = (
            session.query(CellShardGsm).filter(CellShardGsm.cellid.is_(None))
        ).all()
        assert result == []

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SAWarning)
            session.add(
                CellShardGsm(
                    cellid=None,
                    radio=Radio.gsm,
                    mcc=GB_MCC,
                    mnc=GB_MNC,
                    lac=123,
                    cid=2345,
                )
            )
            with pytest.raises(Exception):
                session.flush()

    def test_cellid_too_short(self, session):
        query = session.query(CellShardGsm).filter(CellShardGsm.cellid == (1, 2))
        pytest.raises(Exception, query.first)

    def test_region(self, session):
        cellid = encode_cellid(Radio.gsm, GB_MCC, GB_MNC, 123, 2345)
        session.add(
            CellShard.create(
                cellid=cellid,
                lat=GB_LAT,
                lon=GB_LON,
                region=None,
                radio=Radio.gsm,
                mcc=GB_MCC,
                mnc=GB_MNC,
                lac=123,
                cid=2345,
            )
        )
        session.flush()

        result = session.query(CellShardGsm).first()
        assert result.region == "GB"

    def test_blocked(self):
        today = util.utcnow()
        two_weeks = today - timedelta(days=14)
        assert not station_blocked(CellShardGsm())

        assert station_blocked(CellShardGsm(created=two_weeks, block_count=1))
        assert station_blocked(
            CellShardGsm(created=today - timedelta(30), block_count=1)
        )
        assert not station_blocked(
            CellShardGsm(created=today - timedelta(45), block_count=1)
        )
        assert station_blocked(
            CellShardGsm(created=today - timedelta(45), block_count=2)
        )
        assert not station_blocked(
            CellShardGsm(created=today - timedelta(105), block_count=3)
        )

        assert station_blocked(CellShardGsm(created=two_weeks, block_last=today.date()))
        assert not station_blocked(
            CellShardGsm(created=two_weeks, block_last=two_weeks.date())
        )
        assert station_blocked(
            CellShardGsm(created=two_weeks, block_last=two_weeks.date()),
            two_weeks.date(),
        )


class TestCellArea(object):
    def test_areaid(self, session):
        areaid = (Radio.gsm, GB_MCC, GB_MNC, 1)
        session.add(
            CellArea(areaid=areaid, radio=Radio.wcdma, mcc=GB_MCC, mnc=GB_MNC, lac=1234)
        )
        session.flush()

        result = session.query(CellArea).first()
        assert result.areaid == (Radio.gsm, GB_MCC, GB_MNC, 1)

        result = (session.query(CellArea).filter(CellArea.areaid == areaid)).first()
        assert result.areaid == (Radio.gsm, GB_MCC, GB_MNC, 1)

        query = session.query(CellArea).filter(CellArea.areaid == (1, 2))
        pytest.raises(Exception, query.first)

    def test_areaid_bytes(self, session):
        areaid = encode_cellarea(Radio.gsm, GB_MCC, GB_MNC, 1)
        session.add(
            CellArea(areaid=areaid, radio=Radio.wcdma, mcc=GB_MCC, mnc=GB_MNC, lac=1234)
        )
        session.flush()

        result = session.query(CellArea).first()
        assert result.areaid == (Radio.gsm, GB_MCC, GB_MNC, 1)

        result = (session.query(CellArea).filter(CellArea.areaid == areaid)).first()
        assert result.areaid == (Radio.gsm, GB_MCC, GB_MNC, 1)

    def test_areaid_null(self, session):
        result = (session.query(CellArea).filter(CellArea.areaid.is_(None))).all()
        assert result == []

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SAWarning)
            session.add(
                CellArea(
                    areaid=None, radio=Radio.wcdma, mcc=GB_MCC, mnc=GB_MNC, lac=1234
                )
            )
            with pytest.raises(Exception):
                session.flush()

    def test_areaid_derived(self, session):
        session.add(
            CellArea.create(radio=Radio.wcdma, mcc=GB_MCC, mnc=GB_MNC, lac=1234)
        )
        session.flush()

        result = session.query(CellArea).first()
        assert result.areaid == (Radio.wcdma, GB_MCC, GB_MNC, 1234)

    def test_areaid_explicit(self, session):
        session.add(
            CellArea.create(
                areaid=(Radio.gsm, GB_MCC, GB_MNC, 1),
                radio=Radio.wcdma,
                mcc=GB_MCC,
                mnc=GB_MNC,
                lac=1234,
            )
        )
        session.flush()

        result = session.query(CellArea).first()
        assert result.areaid == (Radio.wcdma, GB_MCC, GB_MNC, 1234)

    def test_areaid_unhex(self, session):
        value = """\
unhex(concat(
lpad(hex({radio}), 2, 0),
lpad(hex({mcc}), 4, 0),
lpad(hex({mnc}), 4, 0),
lpad(hex({lac}), 4, 0))),
{radio}, {mcc}, {mnc}, {lac}
""".format(
            radio=int(Radio.gsm), mcc=310, mnc=1, lac=65534
        )
        stmt = (
            "insert into cell_area " "(areaid, radio, mcc, mnc, lac) " "values (%s)"
        ) % value
        session.execute(stmt)
        session.flush()
        cell = session.query(CellArea).one()
        assert cell.areaid == (Radio.gsm, 310, 1, 65534)

    def test_areaid_hex(self, session):
        value = """\
cast(conv(substr(hex(`areaid`), 1, 2), 16, 10) as unsigned),
cast(conv(substr(hex(`areaid`), 3, 4), 16, 10) as unsigned),
cast(conv(substr(hex(`areaid`), 7, 4), 16, 10) as unsigned),
cast(conv(substr(hex(`areaid`), 11, 4), 16, 10) as unsigned)
"""
        session.add(
            CellArea(
                areaid=(Radio.gsm, 310, 1, 65534),
                radio=Radio.gsm,
                mcc=310,
                mnc=1,
                lac=65534,
            )
        )
        session.flush()
        stmt = "select %s from cell_area" % value
        row = session.execute(stmt).fetchone()
        assert row == (0, 310, 1, 65534)

    def test_invalid(self):
        assert CellArea.validate({"radio": "invalid"}) is None

    def test_region(self, session):
        areaid = encode_cellarea(Radio.gsm, GB_MCC, GB_MNC, 123)
        session.add(
            CellArea.create(
                areaid=areaid,
                lat=GB_LAT,
                lon=GB_LON,
                region=None,
                radio=Radio.gsm,
                mcc=GB_MCC,
                mnc=GB_MNC,
                lac=123,
            )
        )
        session.flush()

        result = session.query(CellArea).first()
        assert result.region == "GB"

    def test_fields(self, session):
        session.add(
            CellArea.create(
                areaid=(Radio.wcdma, GB_MCC, GB_MNC, 1234),
                radio=Radio.wcdma,
                mcc=GB_MCC,
                mnc=GB_MNC,
                lac=1234,
                lat=GB_LAT,
                lon=GB_LON,
                region="GB",
                radius=10,
                avg_cell_radius=10,
                num_cells=15,
            )
        )
        session.flush()

        result = session.query(CellArea).first()
        assert result.areaid == (Radio.wcdma, GB_MCC, GB_MNC, 1234)
        assert result.radio is Radio.wcdma
        assert result.mcc == GB_MCC
        assert result.mnc == GB_MNC
        assert result.lac == 1234
        assert result.lat == GB_LAT
        assert result.lon == GB_LON
        assert result.radius == 10
        assert result.region == "GB"
        assert result.avg_cell_radius == 10
        assert result.num_cells == 15
