from datetime import datetime
from datetime import timedelta
from uuid import uuid4

from ichnaea.db import (
    Measure,
    Score,
    User,
    Stat,
    STAT_TYPE,
)
from ichnaea.tests.base import DBTestCase


class TestStats(DBTestCase):

    def test_global_stats(self):
        from ichnaea.content.stats import global_stats
        session = self.db_master_session
        day = datetime.utcnow().date() - timedelta(1)
        day2 = day - timedelta(1)
        stats = [
            Stat(key=STAT_TYPE['location'], time=day, value=3),
            Stat(key=STAT_TYPE['cell'], time=day, value=4),
            Stat(key=STAT_TYPE['cell'], time=day2, value=2),
            Stat(key=STAT_TYPE['wifi'], time=day, value=3),
            Stat(key=STAT_TYPE['wifi'], time=day2, value=0),
            Stat(key=STAT_TYPE['unique_cell'], time=day, value=3),
            Stat(key=STAT_TYPE['unique_wifi'], time=day, value=2),
        ]
        session.add_all(stats)
        session.commit()

        result = global_stats(session)
        self.assertDictEqual(result, {'location': 3, 'cell': 6,
                             'unique-cell': 3, 'wifi': 3, 'unique-wifi': 2})

    def test_histogram(self):
        from ichnaea.content.stats import histogram
        session = self.db_master_session
        today = datetime.utcnow().date()
        one_day = (today - timedelta(1)).strftime('%Y-%m-%d')
        two_days = (today - timedelta(2)).strftime('%Y-%m-%d')
        long_ago = (today - timedelta(40)).strftime('%Y-%m-%d')
        today = today.strftime('%Y-%m-%d')
        stats = [
            Stat(time=long_ago, value=1),
            Stat(time=two_days, value=3),
            Stat(time=one_day, value=4),
            Stat(time=today, value=2),
        ]
        for stat in stats:
            stat.name = 'location'
        session.add_all(stats)
        session.commit()
        result = histogram(session)
        self.assertEqual(result, [
            {'num': 4, 'day': two_days},
            {'num': 8, 'day': one_day},
        ])

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
