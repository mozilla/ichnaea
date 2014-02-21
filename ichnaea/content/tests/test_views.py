from datetime import datetime
from datetime import timedelta

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
from ichnaea.heka_logging import RAVEN_ERROR
from ichnaea.tests.base import AppTestCase


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

    def test_map(self):
        request = DummyRequest()
        inst = self._make_view(request)
        result = inst.map_view()
        self.assertEqual(result['page_title'], 'Map')


class TestFunctionalContent(AppTestCase):

    def test_content_pages(self):
        self.app.get('/', status=200)
        self.app.get('/leaders', status=200)
        self.app.get('/map', status=200)
        self.app.get('/privacy', status=200)
        self.app.get('/stats', status=200)

    def test_favicon(self):
        self.app.get('/favicon.ico', status=200)

    def test_hsts_header(self):
        result = self.app.get('/', status=200)
        self.assertTrue('Strict-Transport-Security' in result.headers)

    def test_not_found(self):
        self.app.get('/nobody-is-home', status=404)

        # We should have caught at least one error here
        find_msg = self.find_heka_messages
        self.assertEquals(
            len(find_msg('sentry', RAVEN_ERROR, field_name='msg')), 1)

        # No counters for URLs that are invalid
        self.assertEquals(
            len(find_msg('counter', 'http.request')), 0)

    def test_robots_txt(self):
        self.app.get('/robots.txt', status=200)

    def test_stats_unique_cell_json(self):
        app = self.app
        today = datetime.utcnow().date()
        yesterday = today - timedelta(1)
        yesterday = yesterday.strftime('%Y-%m-%d')
        session = self.db_slave_session
        stat = Stat(time=yesterday, value=2)
        stat.name = 'unique_cell'
        session.add(stat)
        session.commit()
        result = app.get('/stats_unique_cell.json', status=200)
        self.assertEqual(
            result.json, {'histogram': [
                {'num': 2, 'day': yesterday},
            ]}
        )

    def test_stats_unique_wifi_json(self):
        app = self.app
        today = datetime.utcnow().date()
        yesterday = today - timedelta(1)
        yesterday = yesterday.strftime('%Y-%m-%d')
        session = self.db_slave_session
        stat = Stat(time=yesterday, value=2)
        stat.name = 'unique_wifi'
        session.add(stat)
        session.commit()
        result = app.get('/stats_unique_wifi.json', status=200)
        self.assertEqual(
            result.json, {'histogram': [
                {'num': 2, 'day': yesterday},
            ]}
        )


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
        today = datetime.utcnow().date()
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
        inst = self._make_view(request)
        result = inst.leaders_view()
        self.assertEqual(
            result['leaders1'],
            [{'nickname': u'2', 'num': 5, 'pos': 1},
             {'nickname': u'1', 'num': 3, 'pos': 2}])
        self.assertEqual(
            result['leaders2'],
            [{'nickname': u'0', 'num': 1, 'pos': 3}])

    def test_stats(self):
        day = datetime.utcnow().date() - timedelta(1)
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
        inst = self._make_view(request)
        result = inst.stats_view()
        self.assertEqual(result['page_title'], 'Statistics')
        self.assertEqual(
            result['metrics'], [
                {'name': 'Unique Cells', 'value': '1.00'},
                {'name': 'Cell Observations', 'value': '2.00'},
                {'name': 'Unique Wifi Networks', 'value': '2.00'},
                {'name': 'Wifi Observations', 'value': '2.00'},
            ])


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
