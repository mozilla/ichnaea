# -*- coding: utf-8 -*-
from calendar import timegm
from datetime import date, timedelta

import genc

from ichnaea.models.content import (
    Score,
    ScoreKey,
    User,
    Stat,
    StatKey,
)
from ichnaea.content.stats import (
    global_stats,
    histogram,
    leaders,
    leaders_weekly,
    regions,
    transliterate,
)
from ichnaea.tests.base import (
    DBTestCase,
    TestCase,
)
from ichnaea.tests.factories import RegionStatFactory
from ichnaea import util


def unixtime(value):
    return timegm(value.timetuple()) * 1000


class TestStats(DBTestCase):

    def test_global_stats(self):
        session = self.session
        day = util.utcnow().date() - timedelta(1)
        stats = [
            Stat(key=StatKey.blue, time=day, value=2200000),
            Stat(key=StatKey.cell, time=day, value=6100000),
            Stat(key=StatKey.wifi, time=day, value=3212000),
            Stat(key=StatKey.unique_blue, time=day, value=1100000),
            Stat(key=StatKey.unique_cell, time=day, value=3289900),
            Stat(key=StatKey.unique_cell_ocid, time=day, value=1523000),
            Stat(key=StatKey.unique_wifi, time=day, value=2009000),
        ]
        session.add_all(stats)
        session.commit()

        result = global_stats(session)
        self.assertDictEqual(
            result, {
                'blue': '2.20', 'unique_blue': '1.10',
                'cell': '6.10', 'unique_cell': '3.28',
                'wifi': '3.21', 'unique_wifi': '2.00',
                'unique_cell_ocid': '1.52',
            })

    def test_global_stats_missing_today(self):
        session = self.session
        day = util.utcnow().date() - timedelta(1)
        yesterday = day - timedelta(days=1)
        stats = [
            Stat(key=StatKey.cell, time=yesterday, value=5000000),
            Stat(key=StatKey.cell, time=day, value=6000000),
            Stat(key=StatKey.wifi, time=day, value=3000000),
            Stat(key=StatKey.unique_cell, time=yesterday, value=4000000),
        ]
        session.add_all(stats)
        session.commit()

        result = global_stats(session)
        self.assertDictEqual(
            result, {
                'blue': '0.00', 'unique_blue': '0.00',
                'cell': '6.00', 'unique_cell': '4.00',
                'wifi': '3.00', 'unique_wifi': '0.00',
                'unique_cell_ocid': '0.00',
            })

    def test_histogram(self):
        session = self.session
        today = util.utcnow().date()
        one_day = today - timedelta(days=1)
        two_days = today - timedelta(days=2)
        one_month = today - timedelta(days=35)
        two_months = today - timedelta(days=70)
        long_ago = today - timedelta(days=100)
        stats = [
            Stat(key=StatKey.cell, time=long_ago, value=40),
            Stat(key=StatKey.cell, time=two_months, value=50),
            Stat(key=StatKey.cell, time=one_month, value=60),
            Stat(key=StatKey.cell, time=two_days, value=70),
            Stat(key=StatKey.cell, time=one_day, value=80),
            Stat(key=StatKey.cell, time=today, value=90),
        ]
        session.add_all(stats)
        session.commit()
        result = histogram(session, StatKey.cell, days=90)
        self.assertTrue(
            [unixtime(one_day), 80] in result[0])

        if two_months.month == 12:
            expected = date(two_months.year + 1, 1, 1)
        else:
            expected = date(two_months.year, two_months.month + 1, 1)
        self.assertTrue(
            [unixtime(expected), 50] in result[0])

    def test_histogram_different_stat_name(self):
        session = self.session
        day = util.utcnow().date() - timedelta(days=1)
        stat = Stat(key=StatKey.unique_cell, time=day, value=9)
        session.add(stat)
        session.commit()
        result = histogram(session, StatKey.unique_cell)
        self.assertEqual(result, [[[unixtime(day), 9]]])

    def test_leaders(self):
        session = self.session
        today = util.utcnow().date()
        test_data = []
        for i in range(20):
            test_data.append((u'nick-%s' % i, 30))
        highest = u'nick-high-too-long_'
        highest += (128 - len(highest)) * u'x'
        test_data.append((highest, 40))
        lowest = u'nick-low'
        test_data.append((lowest, 20))
        for nick, value in test_data:
            user = User(nickname=nick)
            session.add(user)
            session.flush()
            score = Score(key=ScoreKey.location,
                          userid=user.id, time=today, value=value)
            session.add(score)
        session.commit()
        # check the result
        result = leaders(session)
        self.assertEqual(len(result), 22)
        self.assertEqual(result[0]['nickname'], highest[:24] + u'...')
        self.assertEqual(result[0]['num'], 40)
        self.assertTrue(lowest in [r['nickname'] for r in result])

    def test_leaders_weekly(self):
        session = self.session
        today = util.utcnow().date()
        test_data = []
        for i in range(1, 11):
            test_data.append((u'nick-%s' % i, i))
        for nick, value in test_data:
            user = User(nickname=nick)
            session.add(user)
            session.flush()
            score = Score(key=ScoreKey.new_cell,
                          userid=user.id, time=today, value=value)
            session.add(score)
            score = Score(key=ScoreKey.new_wifi,
                          userid=user.id, time=today, value=21 - value)
            session.add(score)
        session.commit()

        # check the result
        result = leaders_weekly(session, batch=5)
        self.assertEqual(len(result), 2)
        self.assertEqual(set(result.keys()), set(['new_cell', 'new_wifi']))

        # check the cell scores
        scores = result['new_cell']
        self.assertEqual(len(scores), 5)
        self.assertEqual(scores[0]['nickname'], 'nick-10')
        self.assertEqual(scores[0]['num'], 10)
        self.assertEqual(scores[-1]['nickname'], 'nick-6')
        self.assertEqual(scores[-1]['num'], 6)

        # check the wifi scores
        scores = result['new_wifi']
        self.assertEqual(len(scores), 5)
        self.assertEqual(scores[0]['nickname'], 'nick-1')
        self.assertEqual(scores[0]['num'], 20)
        self.assertEqual(scores[-1]['nickname'], 'nick-5')
        self.assertEqual(scores[-1]['num'], 16)

    def test_regions(self):
        RegionStatFactory(region='DE', gsm=2, wcdma=1, wifi=4)
        RegionStatFactory(region='GB', wifi=1, blue=1)
        RegionStatFactory(region='TW', wcdma=1)
        RegionStatFactory(region='US', gsm=3, blue=2)
        self.session.flush()

        result = regions(self.session)
        expected = set(['DE', 'GB', 'TW', 'US'])
        self.assertEqual(set([r['code'] for r in result]), expected)

        region_results = {}
        for r in result:
            code = r['code']
            region_results[code] = r
            del region_results[code]['code']

        # ensure we use GENC names
        self.assertEqual(region_results['TW']['name'], 'Taiwan')

        # strip out names to make assertion statements shorter
        for code in region_results:
            del region_results[code]['name']

        self.assertEqual(region_results['DE'],
                         {'gsm': 2, 'wcdma': 1, 'lte': 0, 'cell': 3,
                          'blue': 0, 'wifi': 4, 'order': 'germany'})
        self.assertEqual(region_results['GB'],
                         {'gsm': 0, 'wcdma': 0, 'lte': 0, 'cell': 0,
                          'blue': 1, 'wifi': 1, 'order': 'united kin'})
        self.assertEqual(region_results['US'],
                         {'gsm': 3, 'wcdma': 0, 'lte': 0, 'cell': 3,
                          'blue': 2, 'wifi': 0, 'order': 'united sta'})


class TestTransliterate(TestCase):

    def test_ascii(self):
        for record in genc.REGIONS:
            self.assertNotEqual(record.name, '')
            trans = transliterate(record.name)
            non_ascii = [c for c in trans if ord(c) > 127]
            self.assertEqual(non_ascii, [])
