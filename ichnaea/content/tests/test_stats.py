# -*- coding: utf-8 -*-
from calendar import timegm
from datetime import date, timedelta
from mobile_codes import _countries

from ichnaea.content.models import (
    Score,
    User,
    Stat,
    STAT_TYPE,
)
from ichnaea.content.stats import (
    countries,
    global_stats,
    histogram,
    leaders,
    leaders_weekly,
    transliterate,
)
from ichnaea.models import (
    Cell,
    RADIO_TYPE,
)
from ichnaea.tests.base import DBTestCase, TestCase
from ichnaea import util


def unixtime(value):
    return timegm(value.timetuple()) * 1000


class TestStats(DBTestCase):

    def test_global_stats(self):
        session = self.db_master_session
        day = util.utcnow().date() - timedelta(1)
        stats = [
            Stat(key=STAT_TYPE['cell'], time=day, value=6100000),
            Stat(key=STAT_TYPE['wifi'], time=day, value=3212000),
            Stat(key=STAT_TYPE['unique_cell'], time=day, value=3289900),
            Stat(key=STAT_TYPE['unique_ocid_cell'], time=day, value=1523000),
            Stat(key=STAT_TYPE['unique_wifi'], time=day, value=2009000),
        ]
        session.add_all(stats)
        session.commit()

        result = global_stats(session)
        self.assertDictEqual(
            result, {
                'cell': '6.10', 'unique_cell': '3.28',
                'wifi': '3.21', 'unique_wifi': '2.00',
                'unique_ocid_cell': '1.52',
            })

    def test_global_stats_missing_today(self):
        session = self.db_master_session
        day = util.utcnow().date() - timedelta(1)
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
                'wifi': '3.00', 'unique_wifi': '0.00',
                'unique_ocid_cell': '0.00',
            })

    def test_histogram(self):
        session = self.db_master_session
        today = util.utcnow().date()
        one_day = today - timedelta(days=1)
        two_days = today - timedelta(days=2)
        one_month = today - timedelta(days=35)
        two_months = today - timedelta(days=70)
        long_ago = today - timedelta(days=100)
        stats = [
            Stat(name='cell', time=long_ago, value=40),
            Stat(name='cell', time=two_months, value=50),
            Stat(name='cell', time=one_month, value=60),
            Stat(name='cell', time=two_days, value=70),
            Stat(name='cell', time=one_day, value=80),
            Stat(name='cell', time=today, value=90),
        ]
        session.add_all(stats)
        session.commit()
        result = histogram(session, 'cell', days=90)
        self.assertTrue(
            [unixtime(one_day), 80] in result[0])

        if two_months.month == 12:
            expected = date(two_months.year + 1, 1, 1)
        else:
            expected = date(two_months.year, two_months.month + 1, 1)
        self.assertTrue(
            [unixtime(expected), 50] in result[0])

    def test_histogram_different_stat_name(self):
        session = self.db_master_session
        day = util.utcnow().date() - timedelta(days=1)
        stat = Stat(time=day, value=9)
        stat.name = 'unique_cell'
        session.add(stat)
        session.commit()
        result = histogram(session, 'unique_cell')
        self.assertEqual(result, [[[unixtime(day), 9]]])

    def test_leaders(self):
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

    def test_leaders_weekly(self):
        session = self.db_master_session
        test_data = []
        for i in range(1, 11):
            test_data.append((u'nick-%s' % i, i))
        for nick, value in test_data:
            user = User(nickname=nick)
            session.add(user)
            session.flush()
            score = Score(userid=user.id, value=value)
            score.name = 'new_cell'
            session.add(score)
            score = Score(userid=user.id, value=21 - value)
            score.name = 'new_wifi'
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

    def test_countries(self):
        session = self.db_master_session
        test_data = [
            Cell(radio=RADIO_TYPE[''], mcc=208, mnc=1),
            Cell(radio=RADIO_TYPE['gsm'], mcc=1, mnc=1),
            Cell(radio=RADIO_TYPE['lte'], mcc=262, mnc=1),
            Cell(radio=RADIO_TYPE['gsm'], mcc=310, mnc=1),
            Cell(radio=RADIO_TYPE['gsm'], mcc=310, mnc=2),
            Cell(radio=RADIO_TYPE['gsm'], mcc=313, mnc=1),
            Cell(radio=RADIO_TYPE['cdma'], mcc=310, mnc=1),
            Cell(radio=RADIO_TYPE['umts'], mcc=244, mnc=1),
            Cell(radio=RADIO_TYPE['lte'], mcc=244, mnc=1),
        ]
        session.add_all(test_data)
        session.commit()

        # check the result
        expected = set(['ALA', 'BMU', 'DEU', 'FIN', 'GUM', 'PRI', 'USA'])
        result = countries(session)
        self.assertEqual(len(result), len(expected))
        self.assertEqual(set([r['code'] for r in result]), expected)

        country_results = {}
        for r in result:
            code = r['code']
            country_results[code] = r
            del country_results[code]['code']
            del country_results[code]['name']

        # a simple case with a 1:1 mapping of mcc to ISO country code
        self.assertEqual(country_results['DEU'],
                         {'cdma': 0, 'gsm': 0, 'lte': 1, 'total': 1,
                          'umts': 0, 'multiple': False, 'order': 'germany'})

        # mcc 310 is valid for both GUM/USA, 313 only for USA
        self.assertEqual(country_results['USA'],
                         {'cdma': 1, 'gsm': 3, 'lte': 0, 'total': 4,
                          'umts': 0, 'multiple': True, 'order': 'united sta'})
        self.assertEqual(country_results['GUM'],
                         {'cdma': 1, 'gsm': 2, 'lte': 0, 'total': 3,
                          'umts': 0, 'multiple': True, 'order': 'guam'})

        # These two countries share a mcc, so we report the same data
        # for both of them
        self.assertEqual(country_results['FIN'],
                         {'cdma': 0, 'gsm': 0, 'lte': 1, 'total': 2,
                          'umts': 1, 'multiple': True, 'order': 'finland'})
        self.assertEqual(country_results['ALA'],
                         {'cdma': 0, 'gsm': 0, 'lte': 1, 'total': 2,
                          'umts': 1, 'multiple': True, 'order': 'aland isla'})


class TestTransliterate(TestCase):

    def test_countries(self):
        for country in _countries():
            trans = transliterate(country.name)
            non_ascii = [c for c in trans if ord(c) > 127]
            self.assertEqual(len(non_ascii), 0)
