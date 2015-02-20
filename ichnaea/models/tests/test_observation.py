import uuid

from ichnaea.models.cell import RADIO_TYPE
from ichnaea.models.observation import (
    CellObservation,
    WifiObservation,
)
from ichnaea.tests.base import DBTestCase


class TestCellObservation(DBTestCase):

    def test_fields(self):
        report_id = uuid.uuid1()
        cell = CellObservation(
            lat=1.2345678,
            lon=2.3456789,
            report_id=report_id,
            radio=RADIO_TYPE['gsm'],
            mcc=100,
            mnc=5,
            lac=12345,
            cid=234567,
            asu=26,
            signal=-61,
            ta=10,
        )
        session = self.db_master_session
        session.add(cell)
        session.commit()

        result = session.query(CellObservation).first()
        self.assertEqual(result.report_id, report_id)
        self.assertEqual(result.lat, 1.2345678)
        self.assertEqual(result.lon, 2.3456789)
        self.assertEqual(result.radio, RADIO_TYPE['gsm'])
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 12345)
        self.assertEqual(result.cid, 234567)
        self.assertEqual(result.asu, 26)
        self.assertEqual(result.signal, -61)
        self.assertEqual(result.ta, 10)


class TestWifiObservation(DBTestCase):

    def test_fields(self):
        key = "3680873e9b83"
        report_id = uuid.uuid1()
        wifi = WifiObservation(
            lat=1.2345678,
            lon=2.3456789,
            report_id=report_id,
            key=key,
            channel=2412,
            signal=-45,
        )
        session = self.db_master_session
        session.add(wifi)
        session.commit()

        result = session.query(WifiObservation).first()
        self.assertEqual(result.report_id, report_id)
        self.assertEqual(result.lat, 1.2345678)
        self.assertEqual(result.lon, 2.3456789)
        self.assertEqual(result.key, key)
        self.assertEqual(result.channel, 2412)
        self.assertEqual(result.signal, -45)
