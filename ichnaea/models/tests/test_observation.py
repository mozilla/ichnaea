from ichnaea.internaljson import (
    internal_dumps,
    internal_loads,
)
from ichnaea.models import (
    CellObservation,
    Radio,
    WifiObservation,
)
from ichnaea.tests.base import (
    DBTestCase,
    GB_LAT,
    GB_LON,
    GB_MCC,
)
from ichnaea.tests.factories import (
    CellObservationFactory,
    WifiObservationFactory
)


class TestCellObservation(DBTestCase):

    def test_fields(self):
        obs = CellObservation.create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=5, lac=12345, cid=23456,
            lat=GB_LAT, lon=GB_LON,
            asu=26, signal=-61, ta=10)

        self.assertEqual(obs.lat, GB_LAT)
        self.assertEqual(obs.lon, GB_LON)
        self.assertEqual(obs.radio, Radio.gsm)
        self.assertEqual(obs.mcc, GB_MCC)
        self.assertEqual(obs.mnc, 5)
        self.assertEqual(obs.lac, 12345)
        self.assertEqual(obs.cid, 23456)
        self.assertEqual(obs.asu, 26)
        self.assertEqual(obs.signal, -61)
        self.assertEqual(obs.ta, 10)

        self.assertEqual(obs.shard_id, 'gsm')

    def test_internaljson(self):
        obs = CellObservation.create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=5, lac=12345, cid=23456,
            lat=GB_LAT, lon=GB_LON)

        result = internal_loads(internal_dumps(obs))
        self.assertTrue(type(result), CellObservation)
        self.assertTrue(result.accuracy is None)
        self.assertEqual(type(result.radio), Radio)
        self.assertEqual(result.radio, Radio.gsm)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 12345)
        self.assertEqual(result.cid, 23456)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)

    def test_weight(self):
        obs_factory = CellObservationFactory.build
        self.assertAlmostEqual(
            obs_factory(accuracy=None, signal=-80).weight, 1.0)
        self.assertAlmostEqual(
            obs_factory(accuracy=0.0, signal=-80).weight, 1.0)
        self.assertAlmostEqual(
            obs_factory(accuracy=10.0, signal=-80).weight, 1.0)
        self.assertAlmostEqual(
            obs_factory(accuracy=160.0, signal=-80).weight, 0.25, 2)
        self.assertAlmostEqual(
            obs_factory(accuracy=200.0, signal=-80).weight, 0.22, 2)


class TestWifiObservation(DBTestCase):

    def test_invalid(self):
        mac = '3680873e9b83'
        obs = WifiObservation.create(key=mac, lat=0.0, lon=0.0)
        self.assertTrue(obs is None, obs)

    def test_fields(self):
        mac = '3680873e9b83'
        obs = WifiObservation.create(
            key=mac, lat=GB_LAT, lon=GB_LON,
            channel=5, signal=-45)

        self.assertEqual(obs.lat, GB_LAT)
        self.assertEqual(obs.lon, GB_LON)
        self.assertEqual(obs.mac, mac)
        self.assertEqual(obs.channel, 5)
        self.assertEqual(obs.signal, -45)

        self.assertEqual(obs.shard_id, '8')

    def test_internaljson(self):
        mac = '3680873e9b83'
        obs = WifiObservation.create(
            key=mac, lat=GB_LAT, lon=GB_LON)

        result = internal_loads(internal_dumps(obs))
        self.assertTrue(type(result), WifiObservation)
        self.assertTrue(result.accuracy is None)
        self.assertEqual(result.mac, mac)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)

    def test_weight(self):
        obs_factory = WifiObservationFactory.build
        self.assertAlmostEqual(
            obs_factory(accuracy=None, signal=-80).weight, 1.0)
        self.assertAlmostEqual(
            obs_factory(accuracy=0.0, signal=-80).weight, 1.0)
        self.assertAlmostEqual(
            obs_factory(accuracy=10.0, signal=-80).weight, 1.0)
        self.assertAlmostEqual(
            obs_factory(accuracy=40.0, signal=-80).weight, 0.5)
        self.assertAlmostEqual(
            obs_factory(accuracy=100.0, signal=-80).weight, 0.316, 3)

        self.assertAlmostEqual(
            obs_factory(accuracy=10.0, signal=-100).weight, 0.482, 3)
        self.assertAlmostEqual(
            obs_factory(accuracy=10.0, signal=-30).weight, 16.0, 2)
        self.assertAlmostEqual(
            obs_factory(accuracy=10.0, signal=-10).weight, 123.46, 2)

        self.assertAlmostEqual(
            obs_factory(accuracy=40.0, signal=-30).weight, 8.0, 2)
        self.assertAlmostEqual(
            obs_factory(accuracy=100.0, signal=-30).weight, 5.06, 2)
        self.assertAlmostEqual(
            obs_factory(accuracy=100.0, signal=-10).weight, 39.04, 2)
