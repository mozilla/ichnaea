import pytest
from sqlalchemy.exc import SQLAlchemyError

from ichnaea.models import (
    encode_mac,
    ReportSource,
)
from ichnaea.models.blue import (
    BlueShard,
    BlueShard0,
    BlueShardF,
)
from ichnaea.tests.base import (
    DBTestCase,
    GB_LAT,
    GB_LON,
)
from ichnaea import util


class TestBlueShard(DBTestCase):

    def test_shard_id(self):
        assert BlueShard.shard_id('111101123456') == '0'
        assert BlueShard.shard_id('0000f0123456') == 'f'
        assert BlueShard.shard_id('') is None
        assert BlueShard.shard_id(None) is None

        mac = encode_mac('0000f0123456')
        assert BlueShard.shard_id(mac) == 'f'

    def test_shard_model(self):
        assert BlueShard.shard_model('111101123456') is BlueShard0
        assert BlueShard.shard_model('0000f0123456') is BlueShardF
        assert BlueShard.shard_model('') is None
        assert BlueShard.shard_model(None) is None

        mac = encode_mac('0000f0123456')
        assert BlueShard.shard_model(mac) is BlueShardF

    def test_init(self):
        blue = BlueShard0(mac='111101123456')
        self.session.add(blue)
        self.session.flush()

        blues = (self.session.query(BlueShard0)
                             .filter(BlueShard0.mac == '111101123456')).all()
        assert blues[0].mac == '111101123456'

    def test_init_empty(self):
        blue = BlueShard0()
        self.session.add(blue)
        with pytest.raises(SQLAlchemyError):
            self.session.flush()

    def test_init_fail(self):
        blue = BlueShard0(mac='abc')
        self.session.add(blue)
        with pytest.raises(SQLAlchemyError):
            self.session.flush()

    def test_fields(self):
        now = util.utcnow()
        today = now.date()
        self.session.add(BlueShard.create(
            mac='111101123456', created=now, modified=now,
            lat=GB_LAT, max_lat=GB_LAT, min_lat=GB_LAT,
            lon=GB_LON, max_lon=GB_LON, min_lon=GB_LON,
            radius=200, region='GB', samples=10,
            source=ReportSource.gnss, weight=1.5, last_seen=today,
            block_first=today, block_last=today, block_count=1,
            _raise_invalid=True,
        ))
        self.session.flush()

        blue = self.session.query(BlueShard0).first()
        assert blue.mac == '111101123456'
        assert blue.created == now
        assert blue.modified == now
        assert blue.lat == GB_LAT
        assert blue.max_lat == GB_LAT
        assert blue.min_lat == GB_LAT
        assert blue.lon == GB_LON
        assert blue.max_lon == GB_LON
        assert blue.min_lon == GB_LON
        assert blue.radius == 200
        assert blue.region == 'GB'
        assert blue.samples == 10
        assert blue.source == ReportSource.gnss
        assert blue.weight == 1.5
        assert blue.last_seen == today
        assert blue.block_first == today
        assert blue.block_last == today
        assert blue.block_count == 1

    def test_mac_unhex(self):
        stmt = 'insert into blue_shard_0 (mac) values (unhex("111101123456"))'
        self.session.execute(stmt)
        self.session.flush()
        blue = self.session.query(BlueShard0).one()
        assert blue.mac == '111101123456'

    def test_mac_hex(self):
        self.session.add(BlueShard0(mac='111101123456'))
        self.session.flush()
        stmt = 'select hex(`mac`) from blue_shard_0'
        row = self.session.execute(stmt).fetchone()
        assert row == ('111101123456', )

    def test_score(self):
        now = util.utcnow()
        blue = BlueShard.create(
            mac='111101123456', created=now, modified=now,
            radius=10, samples=2,
        )
        assert round(blue.score(now), 2) == 0.1
