from datetime import datetime
from datetime import timedelta

from ichnaea.models import (
    MapStat,
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
        stats = [
            Stat(key=STAT_TYPE['location'], time=day, value=3),
            Stat(key=STAT_TYPE['cell'], time=day, value=6),
            Stat(key=STAT_TYPE['wifi'], time=day, value=3),
            Stat(key=STAT_TYPE['unique_cell'], time=day, value=3),
            Stat(key=STAT_TYPE['unique_wifi'], time=day, value=2),
        ]
        session.add_all(stats)
        session.commit()

        result = global_stats(session)
        self.assertDictEqual(result, {'location': 3, 'cell': 6,
                             'unique_cell': 3, 'wifi': 3, 'unique_wifi': 2})

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
            Stat(time=one_day, value=7),
            Stat(time=today, value=9),
        ]
        for stat in stats:
            stat.name = 'location'
        session.add_all(stats)
        session.commit()
        result = histogram(session, 'location')
        self.assertEqual(result, [
            {'num': 3, 'day': two_days},
            {'num': 7, 'day': one_day},
        ])

    def test_histogram_different_stat_name(self):
        from ichnaea.content.stats import histogram
        session = self.db_master_session
        day = datetime.utcnow().date() - timedelta(1)
        day = day.strftime('%Y-%m-%d')
        stat = Stat(time=day, value=9)
        stat.name = 'unique_cell'
        session.add(stat)
        session.commit()
        result = histogram(session, 'unique_cell')
        self.assertEqual(result, [{'num': 9, 'day': day}])

    def test_map_csv(self):
        from ichnaea.content.stats import map_csv
        session = self.db_master_session
        stats = [
            MapStat(lat=1000, lon=2000, value=101),
            MapStat(lat=2000, lon=3000, value=11),
            MapStat(lat=3000, lon=4000, value=1),
        ]
        session.add_all(stats)
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
            test_data.append((u'nick-%s' % i, 7))
        highest = u'nick-high'
        test_data.append((highest, 10))
        lowest = u'nick-low'
        test_data.append((lowest, 5))
        for nick, value in test_data:
            user = User(nickname=nick)
            session.add(user)
            session.flush()
            score = Score(userid=user.id, value=value)
            session.add(score)
        session.commit()
        # check the result
        result = leaders(session)
        self.assertEqual(len(result), 22)
        self.assertEqual(result[0]['nickname'], highest)
        self.assertEqual(result[0]['num'], 10)
        self.assertTrue(lowest in [r['nickname'] for r in result])
