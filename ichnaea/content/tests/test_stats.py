# -*- coding: utf-8 -*-
from calendar import timegm
from datetime import date, timedelta

import genc

from ichnaea.models.content import (
    Stat,
    StatKey,
)
from ichnaea.content.stats import (
    global_stats,
    histogram,
    regions,
    transliterate,
)
from ichnaea.tests.base import DBTestCase
from ichnaea.tests.factories import RegionStatFactory
from ichnaea import util


def unixtime(value):
    return timegm(value.timetuple()) * 1000


class TestStats(DBTestCase):

    def test_global_stats(self):
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
        self.session.add_all(stats)
        self.session.commit()

        result = global_stats(self.session)
        assert (result == {
            'blue': '2.20', 'unique_blue': '1.10',
            'cell': '6.10', 'unique_cell': '3.28',
            'wifi': '3.21', 'unique_wifi': '2.00',
            'unique_cell_ocid': '1.52',
        })

    def test_global_stats_missing_today(self):
        day = util.utcnow().date() - timedelta(1)
        yesterday = day - timedelta(days=1)
        stats = [
            Stat(key=StatKey.cell, time=yesterday, value=5000000),
            Stat(key=StatKey.cell, time=day, value=6000000),
            Stat(key=StatKey.wifi, time=day, value=3000000),
            Stat(key=StatKey.unique_cell, time=yesterday, value=4000000),
        ]
        self.session.add_all(stats)
        self.session.commit()

        result = global_stats(self.session)
        assert (result == {
            'blue': '0.00', 'unique_blue': '0.00',
            'cell': '6.00', 'unique_cell': '4.00',
            'wifi': '3.00', 'unique_wifi': '0.00',
            'unique_cell_ocid': '0.00',
        })

    def test_histogram(self):
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
        self.session.add_all(stats)
        self.session.commit()
        result = histogram(self.session, StatKey.cell, days=90)
        first_of_month = today.replace(day=1)
        assert [unixtime(first_of_month), 90] in result[0]

        expected = date(two_months.year, two_months.month, 1)
        assert [unixtime(expected), 50] in result[0]

    def test_histogram_different_stat_name(self):
        today = util.utcnow().date()
        stat = Stat(key=StatKey.unique_cell, time=today, value=9)
        self.session.add(stat)
        self.session.commit()
        result = histogram(self.session, StatKey.unique_cell)
        first_of_month = today.replace(day=1)
        assert result == [[[unixtime(first_of_month), 9]]]

    def test_regions(self):
        RegionStatFactory(region='DE', gsm=2, wcdma=1, wifi=4)
        RegionStatFactory(region='GB', wifi=1, blue=1)
        RegionStatFactory(region='TW', wcdma=1)
        RegionStatFactory(region='US', gsm=3, blue=2)
        self.session.flush()

        result = regions(self.session)
        expected = set(['DE', 'GB', 'TW', 'US'])
        assert set([r['code'] for r in result]) == expected

        region_results = {}
        for r in result:
            code = r['code']
            region_results[code] = r
            del region_results[code]['code']

        # ensure we use GENC names
        assert region_results['TW']['name'] == 'Taiwan'

        # strip out names to make assertion statements shorter
        for code in region_results:
            del region_results[code]['name']

        assert (region_results['DE'] ==
                {'gsm': 2, 'wcdma': 1, 'lte': 0, 'cell': 3,
                 'blue': 0, 'wifi': 4, 'order': 'germany'})
        assert (region_results['GB'] ==
                {'gsm': 0, 'wcdma': 0, 'lte': 0, 'cell': 0,
                 'blue': 1, 'wifi': 1, 'order': 'united kin'})
        assert (region_results['US'] ==
                {'gsm': 3, 'wcdma': 0, 'lte': 0, 'cell': 3,
                 'blue': 2, 'wifi': 0, 'order': 'united sta'})


class TestTransliterate(object):

    def test_ascii(self):
        for record in genc.REGIONS:
            assert record.name != ''
            trans = transliterate(record.name)
            non_ascii = [c for c in trans if ord(c) > 127]
            assert non_ascii == []
