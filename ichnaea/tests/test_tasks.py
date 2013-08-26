from datetime import datetime
from datetime import timedelta

from sqlalchemy.orm.exc import FlushError

from ichnaea.db import (
    Measure,
    Stat,
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

        result = histogram.delay(start=30, end=0)
        added = result.get()
        self.assertEqual(added, 3)

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 3)
        self.assertEqual(stats[0].time, two_days)
        self.assertEqual(stats[1].time, yesterday)
        self.assertEqual(stats[2].time, today)
        self.assertEqual(stats[0].value, 3)
        self.assertEqual(stats[1].value, 1)
        self.assertEqual(stats[2].value, 2)

        # test older time range
        result = histogram.delay(start=60, end=30)
        added = result.get()
        self.assertEqual(added, 1)

        stats = session.query(Stat).order_by(Stat.time).all()
        self.assertEqual(len(stats), 4)
        self.assertEqual(stats[0].time, long_ago)
        self.assertEqual(stats[0].value, 1)

        # test duplicate execution
        result = histogram.delay()
        added = result.get()
        self.assertEqual(added, 0)
