from calendar import timegm
from datetime import timedelta

import boto
from mock import MagicMock, patch
from pyramid.testing import DummyRequest
from pyramid.testing import setUp
from pyramid.testing import tearDown
from unittest2 import TestCase

from ichnaea.content.models import (
    Score,
    Stat,
    STAT_TYPE,
    User,
)
from ichnaea.content.views import (
    LOCAL_TILES,
    LOCAL_TILES_BASE,
)
from ichnaea.heka_logging import RAVEN_ERROR
from ichnaea.tests.base import AppTestCase
from ichnaea import util


class TestContentViews(TestCase):

    def setUp(self):
        request = DummyRequest()
        self.config = setUp(request=request)

    def tearDown(self):
        tearDown()

    def _make_view(self, request):
        from ichnaea.content.views import ContentViews
        return ContentViews(request)

    def test_homepage(self):
        request = DummyRequest()
        inst = self._make_view(request)
        result = inst.homepage_view()
        self.assertEqual(result['page_title'], 'Overview')

    def test_api(self):
        request = DummyRequest()
        inst = self._make_view(request)
        result = inst.api_view()
        self.assertTrue('API' in result['page_title'])

    def test_apps(self):
        request = DummyRequest()
        inst = self._make_view(request)
        result = inst.apps_view()
        self.assertTrue('App' in result['page_title'])

    def test_optout(self):
        request = DummyRequest()
        inst = self._make_view(request)
        result = inst.optout_view()
        self.assertTrue('Opt' in result['page_title'])

    def test_privacy(self):
        request = DummyRequest()
        inst = self._make_view(request)
        result = inst.privacy_view()
        self.assertTrue('Privacy' in result['page_title'])

    def test_map(self):
        request = DummyRequest()
        inst = self._make_view(request)
        result = inst.map_view()
        self.assertEqual(result['page_title'], 'Map')
        self.assertEqual(result['tiles'], LOCAL_TILES)


class TestFunctionalContent(AppTestCase):

    def test_content_pages(self):
        self.app.get('/', status=200)
        self.app.get('/contact', status=200)
        self.app.get('/leaders', status=200)
        self.app.get('/map', status=200)
        self.app.get('/privacy', status=200)
        self.app.get('/stats', status=200)

    def test_csp(self):
        result = self.app.get('/', status=200)
        self.assertTrue('Content-Security-Policy' in result.headers)
        csp = result.headers['Content-Security-Policy']
        # make sure CSP_BASE interpolation worked
        self.assertTrue("'self' https://*.cdn.mozilla.net" in csp)
        # make sure map assets url interpolation worked
        self.assertTrue('127.0.0.1:7001' in csp)

    def test_downloads(self):
        mock_conn = MagicMock(name='conn')
        mock_bucket = MagicMock(name='bucket')
        mock_conn.return_value.lookup.return_value = mock_bucket
        key_prefix = 'export/MLS-diff-cell-export-2014-08-20T'

        class MockKey(object):
            size = 1024

            def __init__(self, name):
                self.name = key_prefix + name

        mock_bucket.list.return_value = [
            MockKey('120000.csv.gz'),
            MockKey('130000.csv.gz'),
            MockKey('140000.csv.gz'),
        ]
        with patch.object(boto, 'connect_s3', mock_conn):
            result = self.app.get('/downloads', status=200)
            self.assertTrue(key_prefix + '120000.csv.gz' in result.text)
            self.assertTrue(key_prefix + '130000.csv.gz' in result.text)
            self.assertTrue(key_prefix + '140000.csv.gz' in result.text)

        # calling the page again should use the cache
        with patch.object(boto, 'connect_s3', mock_conn):
            result = self.app.get('/downloads', status=200)
            self.assertTrue(key_prefix + '120000.csv.gz' in result.text)

        # The mock / S3 API was only called once
        self.assertEqual(len(mock_bucket.list.mock_calls), 1)

    def test_favicon(self):
        self.app.get('/favicon.ico', status=200)

    def test_touchicon(self):
        self.app.get('/apple-touch-icon-precomposed.png', status=200)

    def test_hsts_header(self):
        result = self.app.get('/', status=200)
        self.assertTrue('Strict-Transport-Security' in result.headers)

    def test_frame_options_header(self):
        result = self.app.get('/', status=200)
        self.assertTrue('X-Frame-Options' in result.headers)

    def test_not_found(self):
        self.app.get('/nobody-is-home', status=404)

        self.check_stats(
            # No counters for URLs that are invalid
            counter=[('request.nobody-is-home.404', 0)],

            # No timers for invalid urls either
            timer=[('request.nobody-is-home', 0)])

        self.check_expected_heka_messages(
            # No tracebacks for 404's
            sentry=[('msg', RAVEN_ERROR, 0)])

    def test_image_file(self):
        self.app.get('/static/css/images/icons-000000@2x.png', status=200)
        quoted_path = 'request.static.css.images.icons-000000-2x.png'
        self.check_stats(
            counter=[(quoted_path + '.200', 1)],
            timer=[(quoted_path, 1)])

    def test_robots_txt(self):
        self.app.get('/robots.txt', status=200)

    def test_map_json(self):
        result = self.app.get('/map.json', status=200)
        self.assertEqual(result.json['tiles_url'], LOCAL_TILES_BASE)

    def test_stats_countries(self):
        self.app.get('/stats/countries', status=200)

    def test_stats_cell_json(self):
        app = self.app
        today = util.utcnow().date()
        yesterday = today - timedelta(1)
        session = self.db_slave_session
        stat = Stat(time=yesterday, value=2)
        stat.name = 'unique_cell'
        session.add(stat)
        session.commit()
        result = app.get('/stats_cell.json', status=200)
        self.assertEqual(
            result.json, {'series': [
                {'data': [[timegm(yesterday.timetuple()) * 1000, 2]],
                 'title': 'MLS Cells'},
            ]}
        )
        second_result = app.get('/stats_cell.json', status=200)
        self.assertEqual(second_result.json, result.json)

    def test_stats_wifi_json(self):
        app = self.app
        today = util.utcnow().date()
        yesterday = today - timedelta(1)
        session = self.db_slave_session
        stat = Stat(time=yesterday, value=2)
        stat.name = 'unique_wifi'
        session.add(stat)
        session.commit()
        result = app.get('/stats_wifi.json', status=200)
        self.assertEqual(
            result.json, {'series': [
                {'data': [[timegm(yesterday.timetuple()) * 1000, 2]],
                 'title': 'MLS WiFi'},
            ]}
        )
        second_result = app.get('/stats_wifi.json', status=200)
        self.assertEqual(second_result.json, result.json)


class TestFunctionalContentViews(AppTestCase):

    def setUp(self):
        AppTestCase.setUp(self)
        request = DummyRequest()
        self.config = setUp(request=request)

    def tearDown(self):
        tearDown()
        AppTestCase.tearDown(self)

    def _make_view(self, request):
        from ichnaea.content.views import ContentViews
        return ContentViews(request)

    def test_leaders(self):
        session = self.db_master_session
        today = util.utcnow().date()
        yesterday = today - timedelta(days=1)
        for i in range(3):
            user = User(nickname=unicode(i))
            session.add(user)
            session.flush()
            score1 = Score(userid=user.id, time=today, value=i)
            score1.name = 'location'
            session.add(score1)
            score2 = Score(userid=user.id, time=yesterday, value=i + 1)
            score2.name = 'location'
            session.add(score2)
        session.commit()
        request = DummyRequest()
        request.db_slave_session = self.db_master_session
        request.registry.redis_client = self.redis_client
        inst = self._make_view(request)
        result = inst.leaders_view()
        self.assertEqual(
            result['leaders1'],
            [{'anchor': u'2', 'nickname': u'2', 'num': 5, 'pos': 1},
             {'anchor': u'1', 'nickname': u'1', 'num': 3, 'pos': 2}])
        self.assertEqual(
            result['leaders2'],
            [{'anchor': u'0', 'nickname': u'0', 'num': 1, 'pos': 3}])

        # call the view again, without a working db session, so
        # we can be sure to use the cached result
        inst = self._make_view(request)
        request.db_slave_session = None
        second_result = inst.leaders_view()
        self.assertEqual(second_result, result)

    def test_leaders_weekly(self):
        session = self.db_master_session
        for i in range(3):
            user = User(nickname=unicode(i))
            session.add(user)
            session.flush()
            score1 = Score(userid=user.id, value=i)
            score1.name = 'new_cell'
            session.add(score1)
            score2 = Score(userid=user.id, value=i)
            score2.name = 'new_wifi'
            session.add(score2)
        session.commit()
        request = DummyRequest()
        request.db_slave_session = self.db_master_session
        request.registry.redis_client = self.redis_client
        inst = self._make_view(request)
        result = inst.leaders_weekly_view()
        for score_name in ('new_cell', 'new_wifi'):
            self.assertEqual(
                result['scores'][score_name]['leaders1'],
                [{'nickname': u'2', 'num': 2, 'pos': 1},
                 {'nickname': u'1', 'num': 1, 'pos': 2}])
            self.assertEqual(
                result['scores'][score_name]['leaders2'],
                [{'nickname': u'0', 'num': 0, 'pos': 3}])

        # call the view again, without a working db session, so
        # we can be sure to use the cached result
        inst = self._make_view(request)
        request.db_slave_session = None
        second_result = inst.leaders_weekly_view()
        self.assertEqual(second_result, result)

    def test_stats(self):
        day = util.utcnow().date() - timedelta(1)
        session = self.db_master_session
        stats = [
            Stat(key=STAT_TYPE['cell'], time=day, value=2000000),
            Stat(key=STAT_TYPE['wifi'], time=day, value=2000000),
            Stat(key=STAT_TYPE['unique_cell'], time=day, value=1000000),
            Stat(key=STAT_TYPE['unique_wifi'], time=day, value=2000000),
        ]
        session.add_all(stats)
        session.commit()
        request = DummyRequest()
        request.db_slave_session = self.db_master_session
        request.registry.redis_client = self.redis_client
        inst = self._make_view(request)
        result = inst.stats_view()
        self.assertEqual(result['page_title'], 'Statistics')
        self.assertEqual(
            result['metrics1'], [
                {'name': 'Unique Cells', 'value': '1.00'},
                {'name': 'Cell Observations', 'value': '2.00'},
            ])
        self.assertEqual(
            result['metrics2'], [
                {'name': 'Unique Wifi Networks', 'value': '2.00'},
                {'name': 'Wifi Observations', 'value': '2.00'},
            ])

        # call the view again, without a working db session, so
        # we can be sure to use the cached result
        inst = self._make_view(request)
        request.db_slave_session = None
        second_result = inst.stats_view()
        self.assertEqual(second_result, result)

    def test_stats_countries(self):
        request = DummyRequest()
        request.db_slave_session = self.db_master_session
        request.registry.redis_client = self.redis_client
        inst = self._make_view(request)
        result = inst.stats_countries_view()
        self.assertEqual(result['page_title'], 'Cell Statistics')

        # call the view again, without a working db session, so
        # we can be sure to use the cached result
        inst = self._make_view(request)
        request.db_slave_session = None
        second_result = inst.stats_countries_view()
        self.assertEqual(second_result, result)


class TestLayout(TestCase):

    def setUp(self):
        request = DummyRequest()
        self.config = setUp(request=request)
        self.config.include('pyramid_chameleon')

    def tearDown(self):
        tearDown()

    def _make_layout(self):
        from ichnaea.content.views import Layout
        return Layout()

    def test_base_template(self):
        from chameleon.zpt.template import Macro
        layout = self._make_layout()
        self.assertEqual(layout.base_template.__class__, Macro)

    def test_base_macros(self):
        from chameleon.zpt.template import Macros
        layout = self._make_layout()
        self.assertEqual(layout.base_macros.__class__, Macros)
