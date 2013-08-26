from datetime import datetime
from datetime import timedelta
from uuid import uuid4

from ichnaea.db import (
    CellMeasure,
    Measure,
    Score,
    User,
    WifiMeasure,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.base import DBTestCase


class TestStats(DBTestCase):

    def test_global_stats(self):
        from ichnaea.content.stats import global_stats
        session = self.db_master_session
        m1 = 10000000
        m2 = 20000000
        m3 = 30000000
        session.add(Measure(lat=m1, lon=m2))
        session.add(Measure(lat=m2, lon=m3))
        session.add(Measure(lat=m2, lon=m3))
        session.add(CellMeasure(lat=m1, lon=m2, mcc=1, mnc=1, lac=2, cid=8))
        session.add(CellMeasure(lat=m1, lon=m2, mcc=1, mnc=1, lac=3, cid=9))
        session.add(CellMeasure(lat=m2, lon=m3, mcc=1, mnc=1, lac=3, cid=9))
        session.add(CellMeasure(lat=m2, lon=m3, mcc=1, mnc=1, lac=4, cid=9))
        session.add(CellMeasure(lat=m2, lon=m3, mcc=1, mnc=1, lac=4, cid=9))
        session.add(CellMeasure(lat=m2, lon=m3, mcc=1, mnc=1, lac=4, cid=9))
        session.add(WifiMeasure(lat=m1, lon=m2, key='a'))
        session.add(WifiMeasure(lat=m2, lon=m3, key='b'))
        session.add(WifiMeasure(lat=m2, lon=m3, key='b'))
        session.commit()
        result = global_stats(session)
        self.assertDictEqual(result, {'location': 3, 'cell': 6,
                             'unique-cell': 3, 'wifi': 3, 'unique-wifi': 2})

    def test_map_csv(self):
        from ichnaea.content.stats import map_csv
        session = self.db_master_session
        wifi = '[{"key": "a"}]'
        measures = [Measure(lat=30000000, lon=40000000, wifi=wifi)]
        for i in range(101):
            measures.append(Measure(lat=10000000, lon=20000000, wifi=wifi))
        for i in range(11):
            measures.append(Measure(lat=20000000, lon=30000000, wifi=wifi))
        session.add_all(measures)
        session.commit()
        result = map_csv(session)
        text = result.replace('\r', '').strip('\n')
        text = text.split('\n')
        self.assertEqual(text, ['lat,lon,value', '1.0,2.0,3', '2.0,3.0,2'])

    def test_leaders(self):
        from ichnaea.content.stats import leaders
        session = self.db_master_session
        test_data = []
        for i in range(20):
            test_data.append((uuid4().hex, 7))
        highest = uuid4().hex
        test_data.append((highest, 10))
        lowest = uuid4().hex
        test_data.append((lowest, 5))
        for uid, value in test_data:
            user = User(token=uid, nickname=u'nick')
            session.add(user)
            session.flush()
            score = Score(userid=user.id, value=value)
            session.add(score)
        session.commit()
        # check the result
        result = leaders(session)
        self.assertEqual(len(result), 10)
        self.assertEqual(result[0]['token'], highest[:8])
        self.assertEqual(result[0]['num'], 10)
        self.assertTrue(lowest not in [r['token'] for r in result])


class TestAsyncStats(CeleryTestCase):

    def test_histogram(self):
        from ichnaea.content.stats import histogram
        from ichnaea import tasks
        session = self.db_master_session
        today = datetime.utcnow().date()
        yesterday = (today - timedelta(1)).strftime('%Y-%m-%d')
        two_days = (today - timedelta(2)).strftime('%Y-%m-%d')
        long_ago = (today - timedelta(40)).strftime('%Y-%m-%d')
        today = today.strftime('%Y-%m-%d')
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

        result = tasks.histogram.delay(start=60)
        added = result.get()
        self.assertEqual(added, 4)

        result = histogram(session)
        self.assertEqual(result, [
            {'num': 4, 'day': two_days},
            {'num': 5, 'day': yesterday},
        ])
