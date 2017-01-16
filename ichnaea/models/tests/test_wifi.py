import warnings

import pytest
from sqlalchemy.exc import (
    SAWarning,
    SQLAlchemyError,
)

from ichnaea.conftest import (
    GB_LAT,
    GB_LON,
)
from ichnaea.models import (
    encode_mac,
    ReportSource,
)
from ichnaea.models.wifi import (
    WifiShard,
    WifiShard0,
    WifiShardF,
)
from ichnaea import util


class TestWifiShard(object):

    def test_shard_id(self):
        assert WifiShard.shard_id('111101123456') == '0'
        assert WifiShard.shard_id('0000f0123456') == 'f'
        assert WifiShard.shard_id('') is None
        assert WifiShard.shard_id(None) is None

        mac = encode_mac('0000f0123456')
        assert WifiShard.shard_id(mac) == 'f'

    def test_shard_model(self):
        assert WifiShard.shard_model('111101123456') is WifiShard0
        assert WifiShard.shard_model('0000f0123456') is WifiShardF
        assert WifiShard.shard_model('') is None
        assert WifiShard.shard_model(None) is None

        mac = encode_mac('0000f0123456')
        assert WifiShard.shard_model(mac) is WifiShardF

    def test_init(self, session):
        wifi = WifiShard0(mac='111101123456')
        session.add(wifi)
        session.flush()

        wifis = (session.query(WifiShard0)
                        .filter(WifiShard0.mac == '111101123456')).all()
        assert wifis[0].mac == '111101123456'

    def test_init_empty(self, session):
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', SAWarning)
            session.add(WifiShard0())
            with pytest.raises(SQLAlchemyError):
                session.flush()

    def test_init_fail(self, session):
        session.add(WifiShard0(mac='abc'))
        with pytest.raises(SQLAlchemyError):
            session.flush()

    def test_fields(self, session):
        now = util.utcnow()
        today = now.date()
        session.add(WifiShard.create(
            mac='111101123456', created=now, modified=now,
            lat=GB_LAT, max_lat=GB_LAT, min_lat=GB_LAT,
            lon=GB_LON, max_lon=GB_LON, min_lon=GB_LON,
            radius=200, region='GB', samples=10,
            source=ReportSource.gnss, weight=1.5, last_seen=today,
            block_first=today, block_last=today, block_count=1,
            _raise_invalid=True,
        ))
        session.flush()

        wifi = session.query(WifiShard0).first()
        assert wifi.mac == '111101123456'
        assert wifi.created == now
        assert wifi.modified == now
        assert wifi.lat == GB_LAT
        assert wifi.max_lat == GB_LAT
        assert wifi.min_lat == GB_LAT
        assert wifi.lon == GB_LON
        assert wifi.max_lon == GB_LON
        assert wifi.min_lon == GB_LON
        assert wifi.radius == 200
        assert wifi.region == 'GB'
        assert wifi.samples == 10
        assert wifi.source == ReportSource.gnss
        assert wifi.weight == 1.5
        assert wifi.last_seen == today
        assert wifi.block_first == today
        assert wifi.block_last == today
        assert wifi.block_count == 1

    def test_mac_unhex(self, session):
        stmt = 'insert into wifi_shard_0 (mac) values (unhex("111101123456"))'
        session.execute(stmt)
        session.flush()
        wifi = session.query(WifiShard0).one()
        assert wifi.mac == '111101123456'

    def test_mac_hex(self, session):
        session.add(WifiShard0(mac='111101123456'))
        session.flush()
        stmt = 'select hex(`mac`) from wifi_shard_0'
        row = session.execute(stmt).fetchone()
        assert row == ('111101123456', )

    def test_score(self):
        now = util.utcnow()
        wifi = WifiShard.create(
            mac='111101123456', created=now, modified=now,
            radius=10, samples=2,
        )
        assert round(wifi.score(now), 2) == 0.1
