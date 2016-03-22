from calendar import timegm
from datetime import timedelta

import boto
from chameleon.zpt.template import Macro
from mock import MagicMock, patch
from pyramid.testing import DummyRequest
from pyramid import testing

from ichnaea.content.views import ContentViews
from ichnaea.models.content import (
    Score,
    ScoreKey,
    Stat,
    StatKey,
    User,
)
from ichnaea.content.views import (
    LOCAL_TILES,
    LOCAL_TILES_BASE,
)
from ichnaea.tests.base import AppTestCase, TestCase
from ichnaea import util


class TestContentViews(TestCase):

    def setUp(self):
        super(TestContentViews, self).setUp()
        request = DummyRequest()
        self.config = testing.setUp(request=request)
        self.config.include('pyramid_chameleon')

    def tearDown(self):
        super(TestContentViews, self).setUp()
        testing.tearDown()

    def _make_view(self):
        request = DummyRequest()
        setattr(request, 'db_ro_session', None)
        setattr(request.registry, 'redis_client', None)
        return ContentViews(request)

    def test_base_template(self):
        self.assertEqual(self._make_view().base_template.__class__, Macro)

    def test_homepage(self):
        result = self._make_view().homepage_view()
        self.assertEqual(result['page_title'], 'Overview')

    def test_api(self):
        result = self._make_view().api_view()
        self.assertTrue('API' in result['page_title'])

    def test_apps(self):
        result = self._make_view().apps_view()
        self.assertTrue('App' in result['page_title'])

    def test_optout(self):
        result = self._make_view().optout_view()
        self.assertTrue('Opt' in result['page_title'])

    def test_privacy(self):
        result = self._make_view().privacy_view()
        self.assertTrue('Privacy' in result['page_title'])

    def test_map(self):
        result = self._make_view().map_view()
        self.assertEqual(result['page_title'], 'Map')
        self.assertEqual(result['tiles'], LOCAL_TILES)


class TestFunctionalContent(AppTestCase):

    def test_content_pages(self):
        self.app.get('/', status=200)
        self.app.get('/contact', status=200)
        self.app.get('/leaders', status=200)
        self.app.get('/leaders/weekly', status=301)
        self.app.get('/map', status=200)
        self.app.get('/privacy', status=200)
        self.app.get('/stats', status=200)
        self.check_stats(counter=[
            ('request', ['path:', 'method:get', 'status:200']),
            ('request', ['path:map', 'method:get', 'status:200']),
        ], timer=[
            ('request', ['path:', 'method:get']),
            ('request', ['path:map', 'method:get']),
        ])

    def test_csp(self):
        result = self.app.get('/', status=200)
        self.assertTrue('Content-Security-Policy' in result.headers)
        csp = result.headers['Content-Security-Policy']
        # make sure CSP_BASE interpolation worked
        self.assertTrue("'self'" in csp)
        # make sure map assets url interpolation worked
        self.assertTrue('127.0.0.1:7001' in csp)

    def test_downloads(self):
        mock_conn = MagicMock(name='conn')
        mock_bucket = MagicMock(name='bucket')
        mock_conn.return_value.lookup.return_value = mock_bucket
        key_prefix = 'export/MLS-'

        class MockKey(object):

            def __init__(self, name, size):
                self.name = key_prefix + name
                self.size = size

        mock_bucket.list.return_value = [
            MockKey('full-cell-export-2016-02-24T000000.csv.gz', 1024),
            MockKey('diff-cell-export-2016-02-26T110000.csv.gz', 1000),
            MockKey('diff-cell-export-2016-02-26T100000.csv.gz', 1000),
            MockKey('full-cell-export-2016-02-26T000000.csv.gz', 8192),
            MockKey('diff-cell-export-2016-02-26T120000.csv.gz', 1000),
        ]
        with patch.object(boto, 'connect_s3', mock_conn):
            result = self.app.get('/downloads', status=200)
            self.assertFalse('0kB' in result.text)
            self.assertTrue('1kB' in result.text)
            self.assertTrue('8kB' in result.text)

        # calling the page again should use the cache
        with patch.object(boto, 'connect_s3', mock_conn):
            result = self.app.get('/downloads', status=200)
            self.assertTrue('1kB' in result.text)

        # The mock / S3 API was only called once
        self.assertEqual(len(mock_bucket.list.mock_calls), 1)

    def test_favicon(self):
        self.app.get('/favicon.ico', status=200)
        self.check_stats(total=0)

    def test_touchicon(self):
        self.app.get('/apple-touch-icon-precomposed.png', status=200)
        self.check_stats(total=0)

    def test_hsts_header(self):
        result = self.app.get('/', status=200)
        self.assertTrue('Strict-Transport-Security' in result.headers)

    def test_frame_options_header(self):
        result = self.app.get('/', status=200)
        self.assertTrue('X-Frame-Options' in result.headers)

    def test_not_found(self):
        self.app.get('/nobody-is-home', status=404)
        self.check_stats(total=0)

    def test_image_file(self):
        self.app.get('/static/css/images/icons-000000@2x.png', status=200)
        self.check_stats(total=0)

    def test_robots_txt(self):
        self.app.get('/robots.txt', status=200)
        self.check_stats(total=0)

    def test_map_json(self):
        result = self.app.get('/map.json', status=200)
        self.assertEqual(result.json['tiles_url'], LOCAL_TILES_BASE)

    def test_stats_regions(self):
        self.app.get('/stats/regions', status=200)

    def test_stats_blue_json(self):
        yesterday = util.utcnow().date() - timedelta(1)
        self.session.add(
            Stat(key=StatKey.unique_blue, time=yesterday, value=2))
        self.session.commit()
        result = self.app.get('/stats_blue.json', status=200)
        self.assertEqual(
            result.json, {'series': [
                {'data': [[timegm(yesterday.timetuple()) * 1000, 2]],
                 'title': 'MLS Bluetooth'},
            ]}
        )
        second_result = self.app.get('/stats_blue.json', status=200)
        self.assertEqual(second_result.json, result.json)

    def test_stats_cell_json(self):
        yesterday = util.utcnow().date() - timedelta(1)
        self.session.add(
            Stat(key=StatKey.unique_cell, time=yesterday, value=2))
        self.session.add(
            Stat(key=StatKey.unique_cell_ocid, time=yesterday, value=5))
        self.session.commit()
        result = self.app.get('/stats_cell.json', status=200)
        self.assertEqual(
            result.json, {'series': [
                {'data': [[timegm(yesterday.timetuple()) * 1000, 2]],
                 'title': 'MLS Cells'},
                {'data': [[timegm(yesterday.timetuple()) * 1000, 5]],
                 'title': 'OCID Cells'},
            ]}
        )
        second_result = self.app.get('/stats_cell.json', status=200)
        self.assertEqual(second_result.json, result.json)

    def test_stats_wifi_json(self):
        yesterday = util.utcnow().date() - timedelta(1)
        self.session.add(
            Stat(key=StatKey.unique_wifi, time=yesterday, value=2))
        self.session.commit()
        result = self.app.get('/stats_wifi.json', status=200)
        self.assertEqual(
            result.json, {'series': [
                {'data': [[timegm(yesterday.timetuple()) * 1000, 2]],
                 'title': 'MLS WiFi'},
            ]}
        )
        second_result = self.app.get('/stats_wifi.json', status=200)
        self.assertEqual(second_result.json, result.json)


class TestFunctionalContentViews(AppTestCase):

    def setUp(self):
        super(TestFunctionalContentViews, self).setUp()
        request = DummyRequest()
        self.config = testing.setUp(request=request)

    def tearDown(self):
        super(TestFunctionalContentViews, self).tearDown()
        testing.tearDown()

    def _make_view(self, request):
        return ContentViews(request)

    def test_leaders(self):
        today = util.utcnow().date()
        yesterday = today - timedelta(days=1)
        for i in range(7, 1, -1):
            user = User(nickname=u'%s' % i)
            self.session.add(user)
            self.session.flush()
            score1 = Score(key=ScoreKey.location,
                           userid=user.id, time=today, value=i)
            self.session.add(score1)
            score2 = Score(key=ScoreKey.location,
                           userid=user.id, time=yesterday, value=i + 1)
            self.session.add(score2)
        self.session.commit()
        request = DummyRequest()
        request.db_ro_session = self.session
        request.registry.redis_client = self.redis_client
        inst = self._make_view(request)
        result = inst.leaders_view()
        self.assertEqual(
            result['leaders1'],
            [{'anchor': u'7', 'nickname': u'7', 'num': 15, 'pos': 1},
             {'anchor': u'6', 'nickname': u'6', 'num': 13, 'pos': 2}])
        self.assertEqual(
            result['leaders2'],
            [{'anchor': u'5', 'nickname': u'5', 'num': 11, 'pos': 3}])

        # call the view again, without a working db session, so
        # we can be sure to use the cached result
        inst = self._make_view(request)
        request.db_ro_session = None
        second_result = inst.leaders_view()
        self.assertEqual(second_result, result)

    def test_stats(self):
        day = util.utcnow().date() - timedelta(1)
        stats = [
            Stat(key=StatKey.blue, time=day, value=2200000),
            Stat(key=StatKey.cell, time=day, value=2000000),
            Stat(key=StatKey.wifi, time=day, value=2000000),
            Stat(key=StatKey.unique_blue, time=day, value=1500000),
            Stat(key=StatKey.unique_cell, time=day, value=1000000),
            Stat(key=StatKey.unique_cell_ocid, time=day, value=1500000),
            Stat(key=StatKey.unique_wifi, time=day, value=2000000),
        ]
        self.session.add_all(stats)
        self.session.commit()
        request = DummyRequest()
        request.db_ro_session = self.session
        request.registry.redis_client = self.redis_client
        inst = self._make_view(request)
        result = inst.stats_view()
        self.assertEqual(result['page_title'], 'Statistics')
        self.assertEqual(
            result['metrics1'], [
                {'name': 'Bluetooth Networks', 'value': '1.50'},
                {'name': 'Bluetooth Observations', 'value': '2.20'},
                {'name': 'Wifi Networks', 'value': '2.00'},
                {'name': 'Wifi Observations', 'value': '2.00'},
            ])
        self.assertEqual(
            result['metrics2'], [
                {'name': 'MLS Cells', 'value': '1.00'},
                {'name': 'MLS Cell Observations', 'value': '2.00'},
                {'name': 'OpenCellID Cells', 'value': '1.50'},
            ])

        # call the view again, without a working db session, so
        # we can be sure to use the cached result
        inst = self._make_view(request)
        request.db_ro_session = None
        second_result = inst.stats_view()
        self.assertEqual(second_result, result)

    def test_stats_regions(self):
        request = DummyRequest()
        request.db_ro_session = self.session
        request.registry.redis_client = self.redis_client
        inst = self._make_view(request)
        result = inst.stats_regions_view()
        self.assertEqual(result['page_title'], 'Region Statistics')

        # call the view again, without a working db session, so
        # we can be sure to use the cached result
        inst = self._make_view(request)
        request.db_ro_session = None
        second_result = inst.stats_regions_view()
        self.assertEqual(second_result, result)
