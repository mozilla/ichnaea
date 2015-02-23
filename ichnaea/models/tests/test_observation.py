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
        cell = CellObservation.create(
            lat=GB_LAT,
            lon=GB_LON,
            report_id=report_id,
            radio=Radio.gsm,
            mcc=GB_MCC,
            mnc=5,
            lac=12345,
            cid=23456,
            asu=26,
            signal=-61,
            ta=10,
        )
        session = self.db_master_session
        session.add(cell)
        session.commit()

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
        wifi = WifiObservation.create(
            lat=GB_LAT,
            lon=GB_LON,
            report_id=report_id,
            key=key,
            channel=5,
            signal=-45,
        )
        session = self.db_master_session
        session.add(wifi)
        session.commit()

        result = session.query(WifiObservation).first()
        self.assertEqual(result.report_id, report_id)
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.key, key)
        self.assertEqual(result.channel, 5)
        self.assertEqual(result.signal, -45)
