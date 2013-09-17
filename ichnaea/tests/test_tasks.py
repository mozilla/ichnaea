from datetime import datetime
from datetime import timedelta

from sqlalchemy.orm.exc import FlushError

from ichnaea.db import (
    Measure,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
)
from ichnaea.tasks import DatabaseTask
from ichnaea.tests.base import CeleryTestCase
from ichnaea.worker import celery


@celery.task(base=DatabaseTask)
def add_measure(lat=0, lon=0, fail_counter=None, fails=10):
    try:
        if fail_counter:
            fail_counter[0] += 1
        with add_measure.db_session() as session:
            measure = Measure(lat=lat, lon=lon)
            session.add(measure)
            if fail_counter:
                session.flush()
                measure2 = Measure(lat=0, lon=0)
                # provoke error via duplicate id
                measure2.id = measure.id
                if fail_counter[0] < fails:
                    session.add(measure2)
            session.commit()
    except Exception as exc:
        raise add_measure.retry(exc=exc)


class TestTaskDatabaseIntegration(CeleryTestCase):

    def test_add_measure(self):
        result = add_measure.delay(lat=12345678, lon=23456789)
        self.assertTrue(result.get() is None)
        self.assertTrue(result.successful())

        session = self.db_master_session
        result = session.query(Measure).first()
        self.assertEqual(result.lat, 12345678)
        self.assertEqual(result.lon, 23456789)

    def test_add_measure_fail(self):
        counter = [0]
        self.assertRaises(
            FlushError, add_measure.delay, fail_counter=counter)
        self.assertEqual(counter[0], 4)

        session = self.db_master_session
        result = session.query(Measure).count()
        self.assertEqual(result, 0)

    def test_add_measure_retry(self):
        counter = [0]
        result = add_measure.delay(fail_counter=counter, fails=1)
        self.assertTrue(result.get() is None)
        self.assertEqual(counter[0], 1)

        session = self.db_master_session
        result = session.query(Measure).count()
        self.assertEqual(result, 1)


class TestBlacklist(CeleryTestCase):

    def test_blacklist_moving_wifis(self):
        from ichnaea.tasks import blacklist_moving_wifis
        session = self.db_master_session
        k1 = "ab1234567890"
        k2 = "cd1234567890"
        k3 = "ef1234567890"
        k4 = "b01234567890"
        k5 = "d21234567890"
        measures = [
            WifiMeasure(lat=10010000, lon=10010000, key=k1),
            WifiMeasure(lat=10020000, lon=10050000, key=k1),
            WifiMeasure(lat=10030000, lon=10090000, key=k1),
            WifiMeasure(lat=20100000, lon=20000000, key=k2),
            WifiMeasure(lat=20200000, lon=20000000, key=k2),
            WifiMeasure(lat=30000000, lon=30000000, key=k3),
            WifiMeasure(lat=-30000000, lon=30000000, key=k3),
            WifiMeasure(lat=-41000000, lon=40000000, key=k4),
            WifiMeasure(lat=-41100000, lon=40000000, key=k4),
            WifiMeasure(lat=50000000, lon=50000000, key=k5),
            WifiMeasure(lat=51000000, lon=50000000, key=k5),
        ]
        session.add_all(measures)
        session.add(WifiBlacklist(key=k5))
        session.commit()

        result = blacklist_moving_wifis.delay(ago=0)
        self.assertEqual(sorted(result.get()), sorted([k2, k3, k4]))

        measures = session.query(WifiBlacklist).all()
        self.assertEqual(len(measures), 4)
        self.assertEqual(set([m.key for m in measures]), set([k2, k3, k4, k5]))

        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 5)
        self.assertEqual(set([m.key for m in measures]), set([k1, k5]))

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
                WifiMeasure(lat=m1, lon=m1, key="a%s1234567890" % i))
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
        self.assertEqual(result.get(), (2, 4))

        result = remove_wifi.delay(wifi_keys)
        self.assertEqual(result.get(), (3, 6))

        result = remove_wifi.delay(wifi_keys)
        self.assertEqual(result.get(), (0, 0))


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
