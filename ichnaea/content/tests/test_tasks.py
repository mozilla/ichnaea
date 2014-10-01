from datetime import timedelta

from ichnaea.content.models import (
    Stat,
    STAT_TYPE,
)
from ichnaea.content.tasks import (
    cell_histogram,
    unique_cell_histogram,
    unique_ocid_cell_histogram,
    unique_wifi_histogram,
    wifi_histogram,
)
from ichnaea.models import (
    Cell,
    CellMeasure,
    OCIDCell,
    Wifi,
    WifiMeasure,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea import util


class TestStats(CeleryTestCase):

    def test_cell_histogram(self):
        session = self.db_master_session
        today = util.utcnow().date()
        yesterday = (today - timedelta(1))
        two_days = (today - timedelta(2))
        long_ago = (today - timedelta(3))
        measures = [
            CellMeasure(lat=1.0, lon=2.0, created=today),
            CellMeasure(lat=1.0, lon=2.0, created=today),
            CellMeasure(lat=1.0, lon=2.0, created=yesterday),
            CellMeasure(lat=1.0, lon=2.0, created=two_days),
            CellMeasure(lat=1.0, lon=2.0, created=two_days),
            CellMeasure(lat=1.0, lon=2.0, created=two_days),
            CellMeasure(lat=1.0, lon=2.0, created=long_ago),
        ]
        session.add_all(measures)
        session.commit()

        cell_histogram.delay(ago=3).get()

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0].key, STAT_TYPE['cell'])
        self.assertEqual(stats[0].time, long_ago)
        self.assertEqual(stats[0].value, 1)

        # fill up newer dates
        cell_histogram.delay(ago=2).get()
        cell_histogram.delay(ago=1).get()
        cell_histogram.delay(ago=0).get()

        # test duplicate execution
        cell_histogram.delay(ago=1).get()

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 4)
        self.assertEqual(stats[0].time, long_ago)
        self.assertEqual(stats[0].value, 1)
        self.assertEqual(stats[1].time, two_days)
        self.assertEqual(stats[1].value, 4)
        self.assertEqual(stats[2].time, yesterday)
        self.assertEqual(stats[2].value, 5)
        self.assertEqual(stats[3].time, today)
        self.assertEqual(stats[3].value, 7)

    def test_unique_cell_histogram(self):
        session = self.db_master_session
        today = util.utcnow().date()
        one_day = (today - timedelta(1))
        two_days = (today - timedelta(2))
        long_ago = (today - timedelta(3))
        cells = [
            Cell(created=long_ago, radio=0, mcc=1, mnc=2, lac=3, cid=4),
            Cell(created=two_days, radio=2, mcc=1, mnc=2, lac=3, cid=4),
            Cell(created=two_days, radio=2, mcc=1, mnc=2, lac=3, cid=5),
            Cell(created=one_day, radio=0, mcc=2, mnc=2, lac=3, cid=5),
            Cell(created=today, radio=0, mcc=1, mnc=3, lac=3, cid=4),
            Cell(created=today, radio=0, mcc=1, mnc=2, lac=4, cid=4),
        ]
        session.add_all(cells)
        session.commit()

        result = unique_cell_histogram.delay(ago=3)
        self.assertEqual(result.get(), 1)

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0].key, STAT_TYPE['unique_cell'])
        self.assertEqual(stats[0].time, long_ago)
        self.assertEqual(stats[0].value, 1)

        # fill up newer dates
        unique_cell_histogram.delay(ago=2).get()
        unique_cell_histogram.delay(ago=1).get()
        unique_cell_histogram.delay(ago=0).get()

        # test duplicate execution
        unique_cell_histogram.delay(ago=1).get()

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 4)
        self.assertEqual(stats[0].time, long_ago)
        self.assertEqual(stats[0].value, 1)
        self.assertEqual(stats[1].time, two_days)
        self.assertEqual(stats[1].value, 3)
        self.assertEqual(stats[2].time, one_day)
        self.assertEqual(stats[2].value, 4)
        self.assertEqual(stats[3].time, today)
        self.assertEqual(stats[3].value, 6)

    def test_unique_ocid_cell_histogram(self):
        session = self.db_master_session
        today = util.utcnow().date()
        one_day = (today - timedelta(1))
        two_days = (today - timedelta(2))
        long_ago = (today - timedelta(3))
        cells = [
            OCIDCell(created=long_ago, radio=0, mcc=1, mnc=2, lac=3, cid=4),
            OCIDCell(created=two_days, radio=2, mcc=1, mnc=2, lac=3, cid=4),
            OCIDCell(created=two_days, radio=2, mcc=1, mnc=2, lac=3, cid=5),
            OCIDCell(created=one_day, radio=0, mcc=2, mnc=2, lac=3, cid=5),
            OCIDCell(created=today, radio=0, mcc=1, mnc=3, lac=3, cid=4),
            OCIDCell(created=today, radio=0, mcc=1, mnc=2, lac=4, cid=4),
        ]
        session.add_all(cells)
        session.commit()

        result = unique_ocid_cell_histogram.delay(ago=3)
        self.assertEqual(result.get(), 1)

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0].key, STAT_TYPE['unique_ocid_cell'])
        self.assertEqual(stats[0].time, long_ago)
        self.assertEqual(stats[0].value, 1)

        # fill up newer dates
        unique_ocid_cell_histogram.delay(ago=2).get()
        unique_ocid_cell_histogram.delay(ago=1).get()
        unique_ocid_cell_histogram.delay(ago=0).get()

        # test duplicate execution
        unique_ocid_cell_histogram.delay(ago=1).get()

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 4)
        self.assertEqual(stats[0].time, long_ago)
        self.assertEqual(stats[0].value, 1)
        self.assertEqual(stats[1].time, two_days)
        self.assertEqual(stats[1].value, 3)
        self.assertEqual(stats[2].time, one_day)
        self.assertEqual(stats[2].value, 4)
        self.assertEqual(stats[3].time, today)
        self.assertEqual(stats[3].value, 6)

    def test_wifi_histogram(self):
        session = self.db_master_session
        today = util.utcnow().date()
        yesterday = (today - timedelta(1))
        two_days = (today - timedelta(2))
        long_ago = (today - timedelta(3))
        measures = [
            WifiMeasure(lat=1.0, lon=2.0, created=today),
            WifiMeasure(lat=1.0, lon=2.0, created=today),
            WifiMeasure(lat=1.0, lon=2.0, created=yesterday),
            WifiMeasure(lat=1.0, lon=2.0, created=two_days),
            WifiMeasure(lat=1.0, lon=2.0, created=two_days),
            WifiMeasure(lat=1.0, lon=2.0, created=two_days),
            WifiMeasure(lat=1.0, lon=2.0, created=long_ago),
        ]
        session.add_all(measures)
        session.commit()

        wifi_histogram.delay(ago=3).get()

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0].key, STAT_TYPE['wifi'])
        self.assertEqual(stats[0].time, long_ago)
        self.assertEqual(stats[0].value, 1)

        # fill in newer dates
        wifi_histogram.delay(ago=2).get()
        wifi_histogram.delay(ago=1).get()
        wifi_histogram.delay(ago=0).get()

        # test duplicate execution
        wifi_histogram.delay(ago=1).get()

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 4)
        self.assertEqual(stats[0].time, long_ago)
        self.assertEqual(stats[0].value, 1)
        self.assertEqual(stats[1].time, two_days)
        self.assertEqual(stats[1].value, 4)
        self.assertEqual(stats[2].time, yesterday)
        self.assertEqual(stats[2].value, 5)
        self.assertEqual(stats[3].time, today)
        self.assertEqual(stats[3].value, 7)

    def test_unique_wifi_histogram(self):
        session = self.db_master_session
        today = util.utcnow().date()
        yesterday = (today - timedelta(1))
        two_days = (today - timedelta(2))
        long_ago = (today - timedelta(3))
        k1 = "ab1234567890"
        k2 = "bc1234567890"
        k3 = "cd1234567890"
        k4 = "de1234567890"
        k5 = "ef1234567890"
        wifis = [
            Wifi(created=long_ago, key=k1),
            Wifi(created=two_days, key=k2),
            Wifi(created=yesterday, key=k3),
            Wifi(created=yesterday, key=k4),
            Wifi(created=today, key=k5),
        ]
        session.add_all(wifis)
        session.commit()

        result = unique_wifi_histogram.delay(ago=3)
        added = result.get()
        self.assertEqual(added, 1)

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0].key, STAT_TYPE['unique_wifi'])
        self.assertEqual(stats[0].time, long_ago)
        self.assertEqual(stats[0].value, 1)

        # fill up newer dates
        unique_wifi_histogram.delay(ago=2).get()
        unique_wifi_histogram.delay(ago=1).get()
        unique_wifi_histogram.delay(ago=0).get()

        # test duplicate execution
        unique_wifi_histogram.delay(ago=1).get()

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 4)
        self.assertEqual(stats[0].time, long_ago)
        self.assertEqual(stats[0].value, 1)
        self.assertEqual(stats[1].time, two_days)
        self.assertEqual(stats[1].value, 2)
        self.assertEqual(stats[2].time, yesterday)
        self.assertEqual(stats[2].value, 4)
        self.assertEqual(stats[3].time, today)
        self.assertEqual(stats[3].value, 5)
