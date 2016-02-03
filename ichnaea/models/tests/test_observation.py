from ichnaea.internaljson import (
    internal_dumps,
    internal_loads,
)
from ichnaea.models import (
    BlueObservation,
    BlueReport,
    CellObservation,
    CellReport,
    Radio,
    Report,
    WifiObservation,
    WifiReport,
)
from ichnaea.tests.base import (
    DBTestCase,
    GB_LAT,
    GB_LON,
    GB_MCC,
)
from ichnaea.tests.factories import (
    BlueObservationFactory,
    CellObservationFactory,
    WifiObservationFactory
)


class TestReport(DBTestCase):

    def test_invalid(self):
        self.assertTrue(Report.create(lat=0.0) is None)
        self.assertTrue(Report.create(lat=0.0, lon='abc') is None)
        self.assertTrue(Report.create(lat=0.0, lon=250.0) is None)

    def test_valid(self):
        self.assertFalse(Report.create(lat=GB_LAT, lon=GB_LON) is None)


class TestBlueObservation(DBTestCase):

    def test_fields(self):
        mac = '3680873e9b83'
        obs = BlueObservation.create(
            key=mac, lat=GB_LAT, lon=GB_LON, signal=-45)

        self.assertEqual(obs.lat, GB_LAT)
        self.assertEqual(obs.lon, GB_LON)
        self.assertEqual(obs.mac, mac)
        self.assertEqual(obs.signal, -45)
        self.assertEqual(obs.shard_id, '8')

    def test_internaljson(self):
        obs = BlueObservationFactory.build(accuracy=None)
        result = internal_loads(internal_dumps(obs))
        self.assertTrue(type(result), BlueObservation)
        self.assertTrue(result.accuracy is None)
        self.assertEqual(result.mac, obs.mac)
        self.assertEqual(result.lat, obs.lat)
        self.assertEqual(result.lon, obs.lon)

    def test_weight(self):
        obs_factory = BlueObservationFactory.build
        self.assertAlmostEqual(obs_factory(
            accuracy=None, signal=-80).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            accuracy=0.0, signal=-80).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            accuracy=10.0, signal=-80).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            accuracy=40.0, signal=-80).weight, 0.5)
        self.assertAlmostEqual(obs_factory(
            accuracy=100.0, signal=-80).weight, 0.316, 3)


class TestBlueReport(DBTestCase):

    def test_invalid(self):
        self.assertTrue(BlueReport.create() is None)
        self.assertTrue(BlueReport.create(key='') is None)
        self.assertTrue(BlueReport.create(key='1234567890123') is None)
        self.assertTrue(BlueReport.create(key='aaaaaaZZZZZZ') is None)

    def test_valid(self):
        self.assertFalse(BlueReport.create(key='3680873e9b83') is None)


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
        obs = CellObservationFactory.build(accuracy=None)
        result = internal_loads(internal_dumps(obs))
        self.assertTrue(type(result), CellObservation)
        self.assertTrue(result.accuracy is None)
        self.assertEqual(type(result.radio), Radio)
        self.assertEqual(result.radio, obs.radio)
        self.assertEqual(result.mcc, obs.mcc)
        self.assertEqual(result.mnc, obs.mnc)
        self.assertEqual(result.lac, obs.lac)
        self.assertEqual(result.cid, obs.cid)
        self.assertEqual(result.lat, obs.lat)
        self.assertEqual(result.lon, obs.lon)

    def test_weight(self):
        obs_factory = CellObservationFactory.build
        self.assertAlmostEqual(obs_factory(
            radio=Radio.gsm, accuracy=None, signal=-95).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.gsm, accuracy=0.0, signal=-95).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.gsm, accuracy=10.0, signal=-95).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.gsm, accuracy=160.0, signal=-95).weight, 0.25, 2)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.gsm, accuracy=200.0, signal=-95).weight, 0.22, 2)

        self.assertAlmostEqual(obs_factory(
            radio=Radio.gsm, accuracy=10.0, signal=-51).weight, 10.17, 2)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.gsm, accuracy=160.0, signal=-51).weight, 2.54, 2)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.gsm, accuracy=10.0, signal=-113).weight, 0.52, 2)

        self.assertAlmostEqual(obs_factory(
            radio=Radio.wcdma, accuracy=10.0, signal=-25).weight, 256.0, 2)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.wcdma, accuracy=160.0, signal=-25).weight, 64.0, 2)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.wcdma, accuracy=10.0, signal=-121).weight, 0.47, 2)

        self.assertAlmostEqual(obs_factory(
            radio=Radio.lte, accuracy=10.0, signal=-43).weight, 47.96, 2)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.lte, accuracy=160.0, signal=-43).weight, 11.99, 2)
        self.assertAlmostEqual(obs_factory(
            radio=Radio.lte, accuracy=10.0, signal=-140).weight, 0.3, 2)


class TestCellReport(DBTestCase):

    def test_invalid(self):
        self.assertTrue(CellReport.create() is None)
        self.assertTrue(CellReport.create(radio=Radio.gsm) is None)

    def test_valid(self):
        self.assertFalse(CellReport.create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=5, lac=12345, cid=23456) is None)


class TestWifiObservation(DBTestCase):

    def test_invalid(self):
        self.assertTrue(WifiObservation.create(
            key='3680873e9b83', lat=0.0, lon=0.0) is None)
        self.assertTrue(WifiObservation.create(
            key='', lat=0.0, lon=0.0) is None)

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
        obs = WifiObservationFactory.build(accuracy=None)
        result = internal_loads(internal_dumps(obs))
        self.assertTrue(type(result), WifiObservation)
        self.assertTrue(result.accuracy is None)
        self.assertEqual(result.mac, obs.mac)
        self.assertEqual(result.lat, obs.lat)
        self.assertEqual(result.lon, obs.lon)

    def test_weight(self):
        obs_factory = WifiObservationFactory.build
        self.assertAlmostEqual(obs_factory(
            accuracy=None, signal=-80).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            accuracy=0.0, signal=-80).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            accuracy=10.0, signal=-80).weight, 1.0)
        self.assertAlmostEqual(obs_factory(
            accuracy=40.0, signal=-80).weight, 0.5)
        self.assertAlmostEqual(obs_factory(
            accuracy=100.0, signal=-80).weight, 0.316, 3)

        self.assertAlmostEqual(obs_factory(
            accuracy=10.0, signal=-100).weight, 0.482, 3)
        self.assertAlmostEqual(obs_factory(
            accuracy=10.0, signal=-30).weight, 16.0, 2)
        self.assertAlmostEqual(obs_factory(
            accuracy=10.0, signal=-10).weight, 123.46, 2)

        self.assertAlmostEqual(obs_factory(
            accuracy=40.0, signal=-30).weight, 8.0, 2)
        self.assertAlmostEqual(obs_factory(
            accuracy=100.0, signal=-30).weight, 5.06, 2)
        self.assertAlmostEqual(obs_factory(
            accuracy=100.0, signal=-10).weight, 39.04, 2)


class TestWifiReport(DBTestCase):

    def test_invalid(self):
        self.assertTrue(WifiReport.create() is None)
        self.assertTrue(WifiReport.create(key='') is None)
        self.assertTrue(WifiReport.create(key='1234567890123') is None)
        self.assertTrue(WifiReport.create(key='aaaaaaZZZZZZ') is None)

    def test_valid(self):
        self.assertFalse(WifiReport.create(key='3680873e9b83') is None)
