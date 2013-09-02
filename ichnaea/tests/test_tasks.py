from datetime import datetime
from datetime import timedelta
from hashlib import sha1

from sqlalchemy.orm.exc import FlushError

from ichnaea.db import (
    CellMeasure,
    Measure,
    Stat,
    STAT_TYPE,
    WifiMeasure,
)
from ichnaea.decimaljson import encode_datetime
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


class TestStats(CeleryTestCase):

    def test_histogram(self):
        from ichnaea.tasks import histogram
        session = self.db_master_session
        today = datetime.utcnow().date()
        yesterday = (today - timedelta(1))
        two_days = (today - timedelta(2))
        long_ago = (today - timedelta(40))
        wifi = '[{"key": "a"}]'
        measures = [
            Measure(lat=10000000, lon=20000000, created=today, wifi=wifi),
            Measure(lat=10000000, lon=20000000, created=today, wifi=wifi),
            Measure(lat=10000000, lon=20000000, created=yesterday, wifi=wifi),
            Measure(lat=10000000, lon=20000000, created=two_days, wifi=wifi),
            Measure(lat=10000000, lon=20000000, created=two_days, wifi=wifi),
            Measure(lat=10000000, lon=20000000, created=two_days, wifi=wifi),
            Measure(lat=10000000, lon=20000000, created=long_ago, wifi=wifi),
        ]
        session.add_all(measures)
        session.commit()

        histogram.delay(ago=40).get()
        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0].key, STAT_TYPE['location'])
        self.assertEqual(stats[0].time, long_ago)
        self.assertEqual(stats[0].value, 1)

        # fill up newer dates
        histogram.delay(ago=2).get()
        histogram.delay(ago=1).get()
        histogram.delay(ago=0).get()

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

        # test duplicate execution
        result = histogram.delay(ago=1)
        self.assertEqual(result.get(), 0)

    def test_cell_histogram(self):
        from ichnaea.tasks import cell_histogram
        session = self.db_master_session
        today = datetime.utcnow().date()
        yesterday = (today - timedelta(1))
        two_days = (today - timedelta(2))
        long_ago = (today - timedelta(40))
        measures = [
            CellMeasure(lat=10000000, lon=20000000, created=today),
            CellMeasure(lat=10000000, lon=20000000, created=today),
            CellMeasure(lat=10000000, lon=20000000, created=yesterday),
            CellMeasure(lat=10000000, lon=20000000, created=two_days),
            CellMeasure(lat=10000000, lon=20000000, created=two_days),
            CellMeasure(lat=10000000, lon=20000000, created=two_days),
            CellMeasure(lat=10000000, lon=20000000, created=long_ago),
        ]
        session.add_all(measures)
        session.commit()

        cell_histogram.delay(ago=40).get()

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0].key, STAT_TYPE['cell'])
        self.assertEqual(stats[0].time, long_ago)
        self.assertEqual(stats[0].value, 1)

        # fill up newer dates
        cell_histogram.delay(ago=2).get()
        cell_histogram.delay(ago=1).get()
        cell_histogram.delay(ago=0).get()

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

        # test duplicate execution
        result = cell_histogram.delay(ago=1)
        self.assertEqual(result.get(), 0)

    def test_unique_cell_histogram(self):
        from ichnaea.tasks import unique_cell_histogram
        session = self.db_master_session
        today = datetime.utcnow().date()
        one_day = (today - timedelta(1))
        two_days = (today - timedelta(2))
        long_ago = (today - timedelta(40))
        measures = [
            CellMeasure(created=long_ago, radio=0, mcc=1, mnc=2, lac=3, cid=4),
            CellMeasure(created=two_days, radio=2, mcc=1, mnc=2, lac=3, cid=4),
            CellMeasure(created=two_days, radio=0, mcc=1, mnc=2, lac=3, cid=4),
            CellMeasure(created=two_days, radio=0, mcc=2, mnc=2, lac=3, cid=4),
            CellMeasure(created=one_day, radio=0, mcc=2, mnc=2, lac=3, cid=5),
            CellMeasure(created=today, radio=0, mcc=1, mnc=3, lac=3, cid=4),
            CellMeasure(created=today, radio=0, mcc=1, mnc=2, lac=4, cid=4),
        ]
        session.add_all(measures)
        session.commit()

        result = unique_cell_histogram.delay(ago=40)
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

        # test duplicate execution
        result = unique_cell_histogram.delay()
        self.assertEqual(result.get(), 0)

    def test_wifi_histogram(self):
        from ichnaea.tasks import wifi_histogram
        session = self.db_master_session
        today = datetime.utcnow().date()
        yesterday = (today - timedelta(1))
        two_days = (today - timedelta(2))
        long_ago = (today - timedelta(40))
        measures = [
            WifiMeasure(lat=10000000, lon=20000000, created=today),
            WifiMeasure(lat=10000000, lon=20000000, created=today),
            WifiMeasure(lat=10000000, lon=20000000, created=yesterday),
            WifiMeasure(lat=10000000, lon=20000000, created=two_days),
            WifiMeasure(lat=10000000, lon=20000000, created=two_days),
            WifiMeasure(lat=10000000, lon=20000000, created=two_days),
            WifiMeasure(lat=10000000, lon=20000000, created=long_ago),
        ]
        session.add_all(measures)
        session.commit()

        wifi_histogram.delay(ago=40).get()

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0].key, STAT_TYPE['wifi'])
        self.assertEqual(stats[0].time, long_ago)
        self.assertEqual(stats[0].value, 1)

        # fill in newer dates
        wifi_histogram.delay(ago=2).get()
        wifi_histogram.delay(ago=1).get()
        wifi_histogram.delay(ago=0).get()

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

        # test duplicate execution
        result = wifi_histogram.delay(ago=1)
        self.assertEqual(result.get(), 0)

    def test_unique_wifi_histogram(self):
        from ichnaea.tasks import unique_wifi_histogram
        session = self.db_master_session
        today = datetime.utcnow().date()
        yesterday = (today - timedelta(1))
        two_days = (today - timedelta(2))
        long_ago = (today - timedelta(40))
        k1 = sha1('1').hexdigest()
        k2 = sha1('2').hexdigest()
        k3 = sha1('3').hexdigest()
        measures = [
            WifiMeasure(lat=10000000, lon=20000000, created=long_ago, key=k1),
            WifiMeasure(lat=10000000, lon=20000000, created=two_days, key=k1),
            WifiMeasure(lat=10000000, lon=20000000, created=two_days, key=k2),
            WifiMeasure(lat=10000000, lon=20000000, created=two_days, key=k1),
            WifiMeasure(lat=10000000, lon=20000000, created=yesterday, key=k3),
            WifiMeasure(lat=10000000, lon=20000000, created=today, key=k2),
            WifiMeasure(lat=10000000, lon=20000000, created=today, key=k3),
        ]
        session.add_all(measures)
        session.commit()

        result = unique_wifi_histogram.delay(ago=40)
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

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 4)
        self.assertEqual(stats[0].time, long_ago)
        self.assertEqual(stats[0].value, 1)
        self.assertEqual(stats[1].time, two_days)
        self.assertEqual(stats[1].value, 2)
        self.assertEqual(stats[2].time, yesterday)
        self.assertEqual(stats[2].value, 3)
        self.assertEqual(stats[3].time, today)
        self.assertEqual(stats[3].value, 3)

        # test duplicate execution
        result = unique_wifi_histogram.delay()
        self.assertEqual(result.get(), 0)


class TestInsert(CeleryTestCase):

    def test_wifi(self):
        from ichnaea.tasks import insert_wifi_measure
        session = self.db_master_session
        utcnow = datetime.utcnow()
        measure = dict(
            id=0, created=encode_datetime(utcnow), lat=10000000, lon=20000000,
            time=encode_datetime(utcnow), accuracy=0, altitude=0,
            altitude_accuracy=0,
        )
        entries = [
            {"key": "ab12", "channel": 11, "signal": -80},
            {"key": "cd34", "channel": 3, "signal": -90},
        ]
        result = insert_wifi_measure.delay(measure, entries)
        self.assertEqual(result.get(), 2)

        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 2)
        self.assertEqual(set([m.key for m in measures]), set(["ab12", "cd34"]))
        self.assertEqual(set([m.channel for m in measures]), set([3, 11]))
        self.assertEqual(set([m.signal for m in measures]), set([-80, -90]))

        # test duplicate execution
        result = insert_wifi_measure.delay(measure, entries)
        self.assertEqual(result.get(), 2)
        # TODO this task isn't idempotent yet
        measures = session.query(WifiMeasure).all()
        self.assertEqual(len(measures), 4)

        # test error case
        entries[0]['id'] = measures[0].id
        result = insert_wifi_measure.delay(measure, entries)
        self.assertEqual(result.get(), 0)
