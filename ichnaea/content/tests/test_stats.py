from datetime import datetime
from datetime import timedelta

from ichnaea.models import (
    Cell,
    RADIO_TYPE,
)

from ichnaea.content.models import (
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
            Stat(key=STAT_TYPE['cell'], time=day, value=6100000),
            Stat(key=STAT_TYPE['wifi'], time=day, value=3212000),
            Stat(key=STAT_TYPE['unique_cell'], time=day, value=3289900),
            Stat(key=STAT_TYPE['unique_wifi'], time=day, value=2009000),
        ]
        session.add_all(stats)
        session.commit()

        result = global_stats(session)
        self.assertDictEqual(
            result, {
                'cell': '6.10', 'unique_cell': '3.28',
                'wifi': '3.21', 'unique_wifi': '2.00'
            })

    def test_global_stats_missing_today(self):
        from ichnaea.content.stats import global_stats
        session = self.db_master_session
        day = datetime.utcnow().date() - timedelta(1)
        yesterday = day - timedelta(days=1)
        stats = [
            Stat(key=STAT_TYPE['cell'], time=yesterday, value=5000000),
            Stat(key=STAT_TYPE['cell'], time=day, value=6000000),
            Stat(key=STAT_TYPE['wifi'], time=day, value=3000000),
            Stat(key=STAT_TYPE['unique_cell'], time=yesterday, value=4000000),
        ]
        session.add_all(stats)
        session.commit()

        result = global_stats(session)
        self.assertDictEqual(
            result, {
                'cell': '6.00', 'unique_cell': '4.00',
                'wifi': '3.00', 'unique_wifi': '0.00'
            })

    def test_histogram(self):
        from ichnaea.content.stats import histogram
        session = self.db_master_session
        today = datetime.utcnow().date()
        one_day = (today - timedelta(1)).strftime('%Y-%m-%d')
        two_days = (today - timedelta(2)).strftime('%Y-%m-%d')
        long_ago = (today - timedelta(25)).strftime('%Y-%m-%d')
        today = today.strftime('%Y-%m-%d')
        stats = [
            Stat(time=long_ago, value=1),
            Stat(time=two_days, value=3),
            Stat(time=one_day, value=7),
            Stat(time=today, value=9),
        ]
        for stat in stats:
            stat.name = 'cell'
        session.add_all(stats)
        session.commit()
        result = histogram(session, 'cell', days=20)
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

    def test_leaders(self):
        from ichnaea.content.stats import leaders
        session = self.db_master_session
        test_data = []
        for i in range(20):
            test_data.append((u'nick-%s' % i, 7))
        highest = u'nick-high-too-long_'
        highest += (128 - len(highest)) * u'x'
        test_data.append((highest, 10))
        lowest = u'nick-low'
        test_data.append((lowest, 5))
        for nick, value in test_data:
            user = User(nickname=nick)
            session.add(user)
            session.flush()
            score = Score(userid=user.id, value=value)
            score.name = 'location'
            session.add(score)
        session.commit()
        # check the result
        result = leaders(session)
        self.assertEqual(len(result), 22)
        self.assertEqual(result[0]['nickname'], highest[:24] + u'...')
        self.assertEqual(result[0]['num'], 10)
        self.assertTrue(lowest in [r['nickname'] for r in result])

    def test_countries(self):
        from ichnaea.content.stats import countries
        session = self.db_master_session
        test_data = [
            Cell(radio=RADIO_TYPE[''], mcc=208, mnc=1),
            Cell(radio=RADIO_TYPE['gsm'], mcc=1, mnc=1),
            Cell(radio=RADIO_TYPE['gsm'], mcc=310, mnc=1),
            Cell(radio=RADIO_TYPE['gsm'], mcc=310, mnc=2),
            Cell(radio=RADIO_TYPE['gsm'], mcc=311, mnc=1),
            Cell(radio=RADIO_TYPE['cdma'], mcc=310, mnc=1),
            Cell(radio=RADIO_TYPE['umts'], mcc=262, mnc=1),
            Cell(radio=RADIO_TYPE['lte'], mcc=262, mnc=1),
        ]
        session.add_all(test_data)
        session.commit()

        # check the result
        result = countries(session)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'Germany')
        self.assertEqual(result[1]['name'], 'United States')

        countries = {}
        for r in result:
            name = r['name']
            countries[name] = r
            del countries[name]['name']

        self.assertEqual(
            countries['United States'],
            {'cdma': 1, 'gsm': 3, 'lte': 0, 'total': 4, 'umts': 0}
        )
        self.assertEqual(
            countries['Germany'],
            {'cdma': 0, 'gsm': 0, 'lte': 1, 'total': 2, 'umts': 1}
        )
