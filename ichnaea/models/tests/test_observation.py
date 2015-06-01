import datetime
import uuid

from ichnaea.customjson import (
    kombu_dumps,
    kombu_loads,
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
from ichnaea import util


class TestCellObservation(DBTestCase):

    def test_fields(self):
        report_id = uuid.uuid1()
        self.session.add(CellObservation.create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=5, lac=12345, cid=23456,
            report_id=report_id, lat=GB_LAT, lon=GB_LON,
            asu=26, signal=-61, ta=10))
        self.session.flush()

        result = self.session.query(CellObservation).first()
        self.assertEqual(result.report_id, report_id)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.radio, Radio.gsm)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 12345)
        self.assertEqual(result.cid, 23456)
        self.assertEqual(result.asu, 26)
        self.assertEqual(result.signal, -61)
        self.assertEqual(result.ta, 10)

    def test_customjson(self):
        now = util.utcnow()
        report_id = uuid.uuid1()
        obs = CellObservation.create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=5, lac=12345, cid=23456,
            report_id=report_id, lat=GB_LAT, lon=GB_LON, created=now)

        json_data = kombu_dumps(obs)
        self.assertTrue('accuracy' not in json_data)

        result = kombu_loads(json_data)
        self.assertTrue(type(result), CellObservation)
        self.assertTrue(result.accuracy is None)
        self.assertEqual(type(result.report_id), uuid.UUID)
        self.assertEqual(result.report_id, report_id)
        self.assertEqual(type(result.radio), Radio)
        self.assertEqual(result.radio, Radio.gsm)
        self.assertEqual(result.mcc, GB_MCC)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 12345)
        self.assertEqual(result.cid, 23456)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(type(result.created), datetime.datetime)
        self.assertEqual(result.created, now)


class TestWifiObservation(DBTestCase):

    def test_fields(self):
        key = '3680873e9b83'
        report_id = uuid.uuid1()
        self.session.add(WifiObservation.create(
            key=key, report_id=report_id, lat=GB_LAT, lon=GB_LON,
            channel=5, signal=-45))
        self.session.flush()

        result = self.session.query(WifiObservation).first()
        self.assertEqual(result.report_id, report_id)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.key, key)
        self.assertEqual(result.channel, 5)
        self.assertEqual(result.signal, -45)

    def test_customjson(self):
        key = '3680873e9b83'
        now = util.utcnow()
        report_id = uuid.uuid1()
        obs = WifiObservation.create(
            key=key, report_id=report_id, lat=GB_LAT, lon=GB_LON,
            created=now)

        json_data = kombu_dumps(obs)
        self.assertTrue('accuracy' not in json_data)

        result = kombu_loads(json_data)
        self.assertTrue(type(result), WifiObservation)
        self.assertTrue(result.accuracy is None)
        self.assertEqual(type(result.report_id), uuid.UUID)
        self.assertEqual(result.report_id, report_id)
        self.assertEqual(result.key, key)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(type(result.created), datetime.datetime)
        self.assertEqual(result.created, now)
