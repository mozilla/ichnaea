from sqlalchemy.exc import (
    IntegrityError,
    SQLAlchemyError,
)

from ichnaea.models.wifi import (
    StationSource,
    Wifi,
    WifiBlocklist,
    WifiShard,
    WifiShard0,
    WifiShardF,
)
from ichnaea.tests.base import (
    DBTestCase,
    GB_LAT,
    GB_LON,
)


class TestWifiShard(DBTestCase):

    def test_shard(self):
        self.assertIs(WifiShard.shard_model('111101123456'), WifiShard0)
        self.assertIs(WifiShard.shard_model('0000f0123456'), WifiShardF)

    def test_shard_empty(self):
        self.assertIs(WifiShard.shard_model(None), None)
        self.assertIs(WifiShard.shard_model(''), None)

    def test_create(self):
        wifi = WifiShard0(mac='111101123456')
        self.session.add(wifi)
        self.session.flush()

        wifis = (self.session.query(WifiShard0)
                             .filter(WifiShard0.mac == '111101123456')).all()
        self.assertEqual(wifis[0].mac, '111101123456')

    def test_create_empty(self):
        wifi = WifiShard0()
        self.session.add(wifi)
        with self.assertRaises(SQLAlchemyError):
            self.session.flush()

    def test_create_fail(self):
        wifi = WifiShard0(mac='abc')
        self.session.add(wifi)
        with self.assertRaises(SQLAlchemyError):
            self.session.flush()

    def test_fields(self):
        self.session.add(WifiShard.shard_model('111101123456')(
            mac='111101123456', lat=GB_LAT, lon=GB_LON, radius=200,
            country='GB', samples=10, source=StationSource.gnss))
        self.session.flush()

        wifi = self.session.query(WifiShard0).first()
        self.assertEqual(wifi.mac, '111101123456')
        self.assertEqual(wifi.lat, GB_LAT)
        self.assertEqual(wifi.lon, GB_LON)
        self.assertEqual(wifi.radius, 200)
        self.assertEqual(wifi.range, 200)
        self.assertEqual(wifi.country, 'GB')
        self.assertEqual(wifi.samples, 10)
        self.assertEqual(wifi.total_measures, 10)
        self.assertEqual(wifi.source, StationSource.gnss)


class TestWifi(DBTestCase):

    def test_fields(self):
        self.session.add(Wifi.create(
            key='3680873e9b83', lat=GB_LAT, lon=GB_LON, range=200))
        self.session.flush()

        result = self.session.query(Wifi).first()
        self.assertEqual(result.key, '3680873e9b83')
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.range, 200)


class TestWifiBlocklist(DBTestCase):

    def test_fields(self):
        self.session.add(WifiBlocklist(key='3680873e9b83', count=2))
        self.session.flush()

        result = self.session.query(WifiBlocklist).first()
        self.assertEqual(result.key, '3680873e9b83')
        self.assertEqual(result.count, 2)

    def test_unique_key(self):
        self.session.add(WifiBlocklist(key='3680873e9b83'))
        self.session.flush()

        self.session.add(WifiBlocklist(key='3680873e9b83'))
        self.assertRaises(IntegrityError, self.session.flush)
