from datetime import datetime
from datetime import timedelta

from ichnaea.models import (
    Cell,
    CellMeasure,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
)
from ichnaea.tests.base import CeleryTestCase


class TestBlacklist(CeleryTestCase):

    def test_blacklist_moving_wifis(self):
        from ichnaea.tasks import blacklist_moving_wifis
        now = datetime.utcnow()
        long_ago = now - timedelta(days=40)
        session = self.db_master_session
        k1 = "ab1234567890"
        k2 = "bc1234567890"
        k3 = "cd1234567890"
        k4 = "de1234567890"
        k5 = "ef1234567890"
        k6 = "fa1234567890"
        measures = [
            WifiMeasure(lat=10010000, lon=10010000, key=k1),
            WifiMeasure(lat=10020000, lon=10050000, key=k1),
            WifiMeasure(lat=10030000, lon=10090000, key=k1),
            WifiMeasure(lat=20100000, lon=20000000, key=k2),
            WifiMeasure(lat=20700000, lon=20000000, key=k2),
            WifiMeasure(lat=30000000, lon=30000000, key=k3),
            WifiMeasure(lat=-30000000, lon=30000000, key=k3),
            WifiMeasure(lat=-41000000, lon=40000000, key=k4),
            WifiMeasure(lat=-41600000, lon=40000000, key=k4),
            WifiMeasure(lat=50000000, lon=50000000, key=k5),
            WifiMeasure(lat=51000000, lon=50000000, key=k5),
            WifiMeasure(lat=69000000, lon=69000000, key=k6, created=long_ago),
            WifiMeasure(lat=60000000, lon=60000000, key=k6),
            WifiMeasure(lat=60010000, lon=60000000, key=k6),
        ]
        session.add_all(measures)
        session.add(WifiBlacklist(key=k5))
        session.commit()

        result = blacklist_moving_wifis.delay(ago=0)
        self.assertEqual(set(result.get()), set([k2, k3, k4]))

        black = session.query(WifiBlacklist).all()
        self.assertEqual(len(black), 4)
        self.assertEqual(set([b.key for b in black]), set([k2, k3, k4, k5]))

        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 14)
        self.assertEqual(
            set([m.key for m in measures]), set([k1, k2, k3, k4, k5, k6]))

        # test duplicate call
        result = blacklist_moving_wifis.delay(ago=0)
        self.assertEqual(result.get(), [])

    def test_schedule_new_moving_wifi_analysis(self):
        from ichnaea.tasks import schedule_new_moving_wifi_analysis
        session = self.db_master_session
        measures = []
        m1 = 10000000
        for i in range(11):
            measures.append(
                WifiMeasure(lat=m1, lon=m1, key="a%02d234567890" % i))
        session.add_all(measures)
        session.flush()

        result = schedule_new_moving_wifi_analysis.delay(ago=0, batch=20)
        self.assertEqual(result.get(), 1)

        result = schedule_new_moving_wifi_analysis.delay(ago=0, batch=11)
        self.assertEqual(result.get(), 1)

        result = schedule_new_moving_wifi_analysis.delay(ago=0, batch=10)
        self.assertEqual(result.get(), 2)

        result = schedule_new_moving_wifi_analysis.delay(ago=0, batch=2)
        self.assertEqual(result.get(), 6)

        result = schedule_new_moving_wifi_analysis.delay(ago=1, batch=2)
        self.assertEqual(result.get(), 0)

    def test_remove_wifi(self):
        from ichnaea.tasks import remove_wifi
        session = self.db_master_session
        measures = []
        wifi_keys = ["a%s1234567890" % i for i in range(5)]
        m1 = 10000000
        m2 = 10000000
        for key in wifi_keys:
            measures.append(Wifi(key=key))
            measures.append(WifiMeasure(lat=m1, lon=m1, key=key))
            measures.append(WifiMeasure(lat=m2, lon=m2, key=key))
        session.add_all(measures)
        session.flush()

        result = remove_wifi.delay(wifi_keys[:2])
        self.assertEqual(result.get(), 2)

        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 3)

        result = remove_wifi.delay(wifi_keys)
        self.assertEqual(result.get(), 3)

        result = remove_wifi.delay(wifi_keys)
        self.assertEqual(result.get(), 0)

        wifis = session.query(Wifi).all()
        self.assertEqual(len(wifis), 0)


class TestCellLocationUpdate(CeleryTestCase):

    def test_cell_location_update(self):
        from ichnaea.tasks import cell_location_update
        now = datetime.utcnow()
        before = now - timedelta(days=1)
        session = self.db_master_session
        k1 = dict(radio=1, mcc=1, mnc=2, lac=3, cid=4)
        k2 = dict(radio=1, mcc=1, mnc=2, lac=6, cid=8)
        data = [
            Cell(new_measures=3, total_measures=3, **k1),
            CellMeasure(lat=10000000, lon=10000000, **k1),
            CellMeasure(lat=10020000, lon=10030000, **k1),
            CellMeasure(lat=10040000, lon=10060000, **k1),
            Cell(lat=20000000, lon=20000000,
                 new_measures=2, total_measures=4, **k2),
            # the lat/lon is bogus and mismatches the line above on purpose
            # to make sure old measures are skipped
            CellMeasure(lat=-10000000, lon=-10000000, created=before, **k2),
            CellMeasure(lat=-10000000, lon=-10000000, created=before, **k2),
            CellMeasure(lat=20020000, lon=20040000, **k2),
            CellMeasure(lat=20020000, lon=20040000, **k2),
        ]
        session.add_all(data)
        session.commit()

        result = cell_location_update.delay(min_new=1)
        self.assertEqual(result.get(), 2)

        cells = session.query(Cell).all()
        self.assertEqual(len(cells), 2)
        self.assertEqual([c.new_measures for c in cells], [0, 0])
        for cell in cells:
            if cell.cid == 4:
                self.assertEqual(cell.lat, 10020000)
                self.assertEqual(cell.lon, 10030000)
            elif cell.cid == 8:
                self.assertEqual(cell.lat, 20010000)
                self.assertEqual(cell.lon, 20020000)


class TestWifiLocationUpdate(CeleryTestCase):

    def test_wifi_location_update(self):
        from ichnaea.tasks import wifi_location_update
        now = datetime.utcnow()
        before = now - timedelta(days=1)
        session = self.db_master_session
        k1 = "ab1234567890"
        k2 = "cd1234567890"
        data = [
            Wifi(key=k1, new_measures=3, total_measures=3),
            WifiMeasure(lat=10000000, lon=10000000, key=k1),
            WifiMeasure(lat=10020000, lon=10030000, key=k1),
            WifiMeasure(lat=10040000, lon=10060000, key=k1),
            Wifi(key=k2, lat=20000000, lon=20000000,
                 new_measures=2, total_measures=4),
            # the lat/lon is bogus and mismatches the line above on purpose
            # to make sure old measures are skipped
            WifiMeasure(lat=-10000000, lon=-10000000, key=k2, created=before),
            WifiMeasure(lat=-10000000, lon=-10000000, key=k2, created=before),
            WifiMeasure(lat=20020000, lon=20040000, key=k2, created=now),
            WifiMeasure(lat=20020000, lon=20040000, key=k2, created=now),
        ]
        session.add_all(data)
        session.commit()

        result = wifi_location_update.delay(min_new=1)
        self.assertEqual(result.get(), 2)

        wifis = dict(session.query(Wifi.key, Wifi).all())
        self.assertEqual(set(wifis.keys()), set([k1, k2]))

        self.assertEqual(wifis[k1].lat, 10020000)
        self.assertEqual(wifis[k1].lon, 10030000)
        self.assertEqual(wifis[k1].new_measures, 0)

        self.assertEqual(wifis[k2].lat, 20010000)
        self.assertEqual(wifis[k2].lon, 20020000)
        self.assertEqual(wifis[k2].new_measures, 0)
