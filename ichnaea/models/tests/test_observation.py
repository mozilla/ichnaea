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


class TestWifiObservation(DBTestCase):

    def test_fields(self):
        key = '3680873e9b83'
        obs = WifiObservation.create(
            key=key, lat=GB_LAT, lon=GB_LON,
            channel=5, signal=-45)

        self.assertEqual(obs.lat, GB_LAT)
        self.assertEqual(obs.lon, GB_LON)
        self.assertEqual(obs.key, key)
        self.assertEqual(obs.channel, 5)
        self.assertEqual(obs.signal, -45)

    def test_internaljson(self):
        key = '3680873e9b83'
        obs = WifiObservation.create(
            key=key, lat=GB_LAT, lon=GB_LON)

        result = internal_loads(internal_dumps(obs))
        self.assertTrue(type(result), WifiObservation)
        self.assertTrue(result.accuracy is None)
        self.assertEqual(result.key, key)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
