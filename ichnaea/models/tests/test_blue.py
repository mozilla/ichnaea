from sqlalchemy.exc import (
    SQLAlchemyError,
)

from ichnaea.models import (
    encode_mac,
    StationSource,
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
        self.assertEqual(BlueShard.shard_id('111101123456'), '0')
        self.assertEqual(BlueShard.shard_id('0000f0123456'), 'f')
        self.assertEqual(BlueShard.shard_id(''), None)
        self.assertEqual(BlueShard.shard_id(None), None)

        mac = encode_mac('0000f0123456')
        self.assertEqual(BlueShard.shard_id(mac), 'f')

    def test_shard_model(self):
        self.assertIs(BlueShard.shard_model('111101123456'), BlueShard0)
        self.assertIs(BlueShard.shard_model('0000f0123456'), BlueShardF)
        self.assertIs(BlueShard.shard_model(''), None)
        self.assertIs(BlueShard.shard_model(None), None)

        mac = encode_mac('0000f0123456')
        self.assertEqual(BlueShard.shard_model(mac), BlueShardF)

    def test_init(self):
        blue = BlueShard0(mac='111101123456')
        self.session.add(blue)
        self.session.flush()

        blues = (self.session.query(BlueShard0)
                             .filter(BlueShard0.mac == '111101123456')).all()
        self.assertEqual(blues[0].mac, '111101123456')

    def test_init_empty(self):
        blue = BlueShard0()
        self.session.add(blue)
        with self.assertRaises(SQLAlchemyError):
            self.session.flush()

    def test_init_fail(self):
        blue = BlueShard0(mac='abc')
        self.session.add(blue)
        with self.assertRaises(SQLAlchemyError):
            self.session.flush()

    def test_fields(self):
        now = util.utcnow()
        today = now.date()
        self.session.add(BlueShard.create(
            mac='111101123456', created=now, modified=now,
            lat=GB_LAT, max_lat=GB_LAT, min_lat=GB_LAT,
            lon=GB_LON, max_lon=GB_LON, min_lon=GB_LON,
            radius=200, region='GB', samples=10,
            source=StationSource.gnss, weight=1.5, last_seen=today,
            block_first=today, block_last=today, block_count=1,
            _raise_invalid=True,
        ))
        self.session.flush()

        blue = self.session.query(BlueShard0).first()
        self.assertEqual(blue.mac, '111101123456')
        self.assertEqual(blue.created, now)
        self.assertEqual(blue.modified, now)
        self.assertEqual(blue.lat, GB_LAT)
        self.assertEqual(blue.max_lat, GB_LAT)
        self.assertEqual(blue.min_lat, GB_LAT)
        self.assertEqual(blue.lon, GB_LON)
        self.assertEqual(blue.max_lon, GB_LON)
        self.assertEqual(blue.min_lon, GB_LON)
        self.assertEqual(blue.radius, 200)
        self.assertEqual(blue.region, 'GB')
        self.assertEqual(blue.samples, 10)
        self.assertEqual(blue.source, StationSource.gnss)
        self.assertEqual(blue.weight, 1.5)
        self.assertEqual(blue.last_seen, today)
        self.assertEqual(blue.block_first, today)
        self.assertEqual(blue.block_last, today)
        self.assertEqual(blue.block_count, 1)

    def test_mac_unhex(self):
        stmt = 'insert into blue_shard_0 (mac) values (unhex("111101123456"))'
        self.session.execute(stmt)
        self.session.flush()
        blue = self.session.query(BlueShard0).one()
        self.assertEqual(blue.mac, '111101123456')

    def test_mac_hex(self):
        self.session.add(BlueShard0(mac='111101123456'))
        self.session.flush()
        stmt = 'select hex(`mac`) from blue_shard_0'
        row = self.session.execute(stmt).fetchone()
        self.assertEqual(row, ('111101123456', ))

    def test_score(self):
        now = util.utcnow()
        blue = BlueShard.create(
            mac='111101123456', created=now, modified=now,
            radius=10, samples=2,
        )
        self.assertAlmostEqual(blue.score(now), 0.1, 2)
