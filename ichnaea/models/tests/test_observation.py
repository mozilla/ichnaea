import datetime
import uuid

from ichnaea.tests.base import DBTestCase


class TestCellMeasure(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import CellMeasure
        return CellMeasure(**kw)

    def test_constructor(self):
        cell = self._make_one()
        self.assertTrue(isinstance(cell.created, datetime.datetime))

    def test_fields(self):
        report_id = uuid.uuid1().bytes
        cell = self._make_one(
            lat=1.2345678,
            lon=2.3456789,
            report_id=report_id,
            radio=0,
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

        result = session.query(cell.__class__).first()
        self.assertEqual(result.report_id, report_id)
        self.assertTrue(isinstance(result.created, datetime.datetime))
        self.assertEqual(result.lat, 1.2345678)
        self.assertEqual(result.lon, 2.3456789)
        self.assertEqual(result.radio, 0)
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 12345)
        self.assertEqual(result.cid, 234567)
        self.assertEqual(result.asu, 26)
        self.assertEqual(result.signal, -61)
        self.assertEqual(result.ta, 10)


class TestWifiMeasure(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import WifiMeasure
        return WifiMeasure(**kw)

    def test_constructor(self):
        wifi = self._make_one()
        self.assertTrue(wifi.id is None)

    def test_fields(self):
        key = "3680873e9b83"
        report_id = uuid.uuid1().bytes
        wifi = self._make_one(
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

        result = session.query(wifi.__class__).first()
        self.assertEqual(result.report_id, report_id)
        self.assertTrue(isinstance(result.created, datetime.datetime))
        self.assertEqual(result.lat, 1.2345678)
        self.assertEqual(result.lon, 2.3456789)
        self.assertEqual(result.key, key)
        self.assertEqual(result.channel, 2412)
        self.assertEqual(result.signal, -45)
