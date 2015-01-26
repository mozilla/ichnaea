import datetime
import uuid

from sqlalchemy.exc import IntegrityError

from ichnaea.models import RADIO_TYPE
from ichnaea.tests.base import DBTestCase


class TestApiKey(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import ApiKey
        return ApiKey(**kw)

    def test_constructor(self):
        key = self._make_one(valid_key='foo')
        self.assertEqual(key.valid_key, 'foo')
        self.assertEqual(key.maxreq, None)

    def test_fields(self):
        key = self._make_one(
            valid_key='foo-bar', maxreq=10, shortname='foo',
            email='Test <test@test.com>', description='A longer text.',
        )
        session = self.db_master_session
        session.add(key)
        session.commit()

        result = session.query(key.__class__).first()
        self.assertEqual(result.valid_key, 'foo-bar')
        self.assertEqual(result.shortname, 'foo')
        self.assertEqual(result.email, 'Test <test@test.com>')
        self.assertEqual(result.description, 'A longer text.')


class TestCell(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import Cell
        return Cell(**kw)

    def test_constructor(self):
        cell = self._make_one()
        self.assertEqual(cell.new_measures, 0)
        self.assertEqual(cell.total_measures, 0)

    def test_fields(self):
        cell = self._make_one(
            radio=1, lat=1.2345678, lon=2.3456789, mcc=100, mnc=5,
            lac=1234, cid=23456, new_measures=2, total_measures=15)
        session = self.db_master_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.lat, 1.2345678)
        self.assertEqual(result.lon, 2.3456789)
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.cid, 23456)
        self.assertEqual(result.new_measures, 2)
        self.assertEqual(result.total_measures, 15)


class TestCellArea(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import CellArea
        return CellArea(**kw)

    def test_constructor(self):
        cell = self._make_one()
        self.assertEqual(cell.range, 0)
        self.assertEqual(cell.avg_cell_range, 0)
        self.assertEqual(cell.num_cells, 0)

    def test_fields(self):
        cell = self._make_one(
            range=10,
            avg_cell_range=10,
            radio=1,
            lac=1234,
            lat=1.2345678,
            lon=2.3456789,
            mcc=100,
            mnc=5,
            num_cells=15,
        )
        session = self.db_master_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.range, 10)
        self.assertEqual(result.avg_cell_range, 10)
        self.assertEqual(result.radio, 1)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.lat, 1.2345678)
        self.assertEqual(result.lon, 2.3456789)
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.num_cells, 15)


class TestOCIDCellArea(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import OCIDCellArea
        return OCIDCellArea(**kw)

    def test_constructor(self):
        cell = self._make_one()
        self.assertEqual(cell.range, 0)
        self.assertEqual(cell.avg_cell_range, 0)
        self.assertEqual(cell.num_cells, 0)

    def test_fields(self):
        cell = self._make_one(
            range=10,
            avg_cell_range=10,
            radio=1,
            lac=1234,
            lat=1.2345678,
            lon=2.3456789,
            mcc=100,
            mnc=5,
            num_cells=15,
        )
        session = self.db_master_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.range, 10)
        self.assertEqual(result.avg_cell_range, 10)
        self.assertEqual(result.radio, 1)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.lat, 1.2345678)
        self.assertEqual(result.lon, 2.3456789)
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.num_cells, 15)


class TestCellMeasure(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import CellMeasure
        return CellMeasure(**kw)

    def test_constructor(self):
        self._make_one()

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


class TestOCIDCell(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import OCIDCell
        return OCIDCell(**kw)

    def test_constructor(self):
        cell = self._make_one()
        self.assertEqual(cell.total_measures, 0)

    def test_fields(self):
        cell = self._make_one(
            radio=RADIO_TYPE['gsm'], mcc=100, mnc=5, lac=1234, cid=23456,
            lat=1.2345678, lon=2.3456789, range=1000, total_measures=15,
        )
        session = self.db_master_session
        session.add(cell)
        session.commit()

        result = session.query(cell.__class__).first()
        self.assertEqual(result.radio, RADIO_TYPE['gsm'])
        self.assertEqual(result.mcc, 100)
        self.assertEqual(result.mnc, 5)
        self.assertEqual(result.lac, 1234)
        self.assertEqual(result.cid, 23456)
        self.assertEqual(result.lat, 1.2345678)
        self.assertEqual(result.lon, 2.3456789)
        self.assertEqual(result.total_measures, 15)
        self.assertEqual(result.min_lat, 1.225567790999991)
        self.assertEqual(result.min_lon, 2.3184002892204245)
        self.assertEqual(result.max_lat, 1.243567809000009)
        self.assertEqual(result.max_lon, 2.372957510779575)


class TestWifi(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import Wifi
        return Wifi(**kw)

    def test_constructor(self):
        wifi = self._make_one()
        self.assertTrue(wifi.key is None)
        self.assertEqual(wifi.new_measures, 0)
        self.assertEqual(wifi.total_measures, 0)

    def test_fields(self):
        key = "3680873e9b83"
        wifi = self._make_one(
            key=key, lat=1.2345678, lon=2.3456789, range=200,
            new_measures=2, total_measures=15,
        )
        session = self.db_master_session
        session.add(wifi)
        session.commit()

        result = session.query(wifi.__class__).first()
        self.assertEqual(result.key, key)
        self.assertEqual(result.lat, 1.2345678)
        self.assertEqual(result.lon, 2.3456789)
        self.assertEqual(result.range, 200)
        self.assertEqual(result.new_measures, 2)
        self.assertEqual(result.total_measures, 15)


class TestWifiBlacklist(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.models import WifiBlacklist
        return WifiBlacklist(**kw)

    def test_constructor(self):
        wifi = self._make_one()
        self.assertTrue(wifi.key is None)
        self.assertTrue(wifi.time is not None)
        self.assertTrue(wifi.count is not None)

    def test_fields(self):
        key = "3680873e9b83"
        wifi = self._make_one(key=key)
        session = self.db_master_session
        session.add(wifi)
        session.commit()

        result = session.query(wifi.__class__).first()
        self.assertEqual(result.key, key)
        self.assertTrue(isinstance(result.time, datetime.datetime))
        self.assertTrue(isinstance(result.count, int))

    def test_unique_key(self):
        key = "3680873e9b83"
        wifi1 = self._make_one(key=key)
        session = self.db_master_session
        session.add(wifi1)
        session.commit()

        wifi2 = self._make_one(key=key)
        session.add(wifi2)
        self.assertRaises(IntegrityError, session.commit)


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
