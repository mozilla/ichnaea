import uuid

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
        report_id = uuid.uuid1()
        session = self.session
        session.add(CellObservation.create(
            radio=Radio.gsm, mcc=GB_MCC, mnc=5, lac=12345, cid=23456,
            report_id=report_id, lat=GB_LAT, lon=GB_LON,
            asu=26, signal=-61, ta=10))
        session.flush()

        result = session.query(CellObservation).first()
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


class TestWifiObservation(DBTestCase):

    def test_fields(self):
        key = "3680873e9b83"
        report_id = uuid.uuid1()
        session = self.session
        session.add(WifiObservation.create(
            key=key, report_id=report_id, lat=GB_LAT, lon=GB_LON,
            channel=5, signal=-45))
        session.flush()

        result = session.query(WifiObservation).first()
        self.assertEqual(result.report_id, report_id)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.key, key)
        self.assertEqual(result.channel, 5)
        self.assertEqual(result.signal, -45)
