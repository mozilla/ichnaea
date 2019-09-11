import warnings

import pytest
from sqlalchemy.exc import SAWarning, SQLAlchemyError

from ichnaea.conftest import GB_LAT, GB_LON
from ichnaea.models import encode_mac, ReportSource
from ichnaea.models.blue import BlueShard, BlueShard0, BlueShardF
from ichnaea import util


class TestBlueShard(object):
    def test_shard_id(self):
        assert BlueShard.shard_id("111101123456") == "0"
        assert BlueShard.shard_id("0000f0123456") == "f"
        assert BlueShard.shard_id("") is None
        assert BlueShard.shard_id(None) is None

        mac = encode_mac("0000f0123456")
        assert BlueShard.shard_id(mac) == "f"

    def test_shard_model(self):
        assert BlueShard.shard_model("111101123456") is BlueShard0
        assert BlueShard.shard_model("0000f0123456") is BlueShardF
        assert BlueShard.shard_model("") is None
        assert BlueShard.shard_model(None) is None

        mac = encode_mac("0000f0123456")
        assert BlueShard.shard_model(mac) is BlueShardF

    def test_init(self, session):
        blue = BlueShard0(mac="111101123456")
        session.add(blue)
        session.flush()

        blues = (
            session.query(BlueShard0).filter(BlueShard0.mac == "111101123456")
        ).all()
        assert blues[0].mac == "111101123456"

    def test_init_empty(self, session):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SAWarning)
            session.add(BlueShard0())
            with pytest.raises(SQLAlchemyError):
                session.flush()

    def test_init_fail(self, session):
        session.add(BlueShard0(mac="abc"))
        with pytest.raises(SQLAlchemyError):
            session.flush()

    def test_fields(self, session):
        now = util.utcnow()
        today = now.date()
        session.add(
            BlueShard.create(
                mac="111101123456",
                created=now,
                modified=now,
                lat=GB_LAT,
                max_lat=GB_LAT,
                min_lat=GB_LAT,
                lon=GB_LON,
                max_lon=GB_LON,
                min_lon=GB_LON,
                radius=200,
                region="GB",
                samples=10,
                source=ReportSource.gnss,
                weight=1.5,
                last_seen=today,
                block_first=today,
                block_last=today,
                block_count=1,
                _raise_invalid=True,
            )
        )
        session.flush()

        blue = session.query(BlueShard0).first()
        assert blue.mac == "111101123456"
        assert blue.created == now
        assert blue.modified == now
        assert blue.lat == GB_LAT
        assert blue.max_lat == GB_LAT
        assert blue.min_lat == GB_LAT
        assert blue.lon == GB_LON
        assert blue.max_lon == GB_LON
        assert blue.min_lon == GB_LON
        assert blue.radius == 200
        assert blue.region == "GB"
        assert blue.samples == 10
        assert blue.source == ReportSource.gnss
        assert blue.weight == 1.5
        assert blue.last_seen == today
        assert blue.block_first == today
        assert blue.block_last == today
        assert blue.block_count == 1

    def test_mac_unhex(self, session):
        stmt = 'insert into blue_shard_0 (mac) values (unhex("111101123456"))'
        session.execute(stmt)
        session.flush()
        blue = session.query(BlueShard0).one()
        assert blue.mac == "111101123456"

    def test_mac_hex(self, session):
        session.add(BlueShard0(mac="111101123456"))
        session.flush()
        stmt = "select hex(`mac`) from blue_shard_0"
        row = session.execute(stmt).fetchone()
        assert row == ("111101123456",)
