from datetime import datetime
from datetime import timedelta

from pyramid.testing import DummyRequest
from pyramid.testing import setUp
from pyramid.testing import tearDown
from unittest2 import TestCase

from ichnaea.db import (
    Measure,
    Score,
    Stat,
    STAT_TYPE,
    User,
)
from ichnaea.tests.base import (
    AppTestCase,
)


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
        self.assertEqual(result['page_title'], 'Coverage Map')


class TestFunctionalContent(AppTestCase):

    def test_favicon(self):
        self.app.get('/favicon.ico', status=200)

    def test_homepage(self):
        result = self.app.get('/', status=200)
        self.assertTrue('Strict-Transport-Security' in result.headers)

    def test_leaders(self):
        self.app.get('/leaders', status=200)

    def test_not_found(self):
        self.app.get('/nobody-is-home', status=404)

    def test_map(self):
        self.app.get('/map', status=200)

    def test_map_csv(self):
        app = self.app
        session = self.db_slave_session
        wifi = '[{"key": "a"}]'
        measures = []
        for i in range(11):
            measures.append(Measure(lat=20000000, lon=30000000, wifi=wifi))
        session.add_all(measures)
        session.commit()
        result = app.get('/map.csv', status=200)
        self.assertEqual(result.content_type, 'text/plain')
        text = result.text.replace('\r', '').strip('\n')
        text = text.split('\n')
        self.assertEqual(text, ['lat,lon,value', '2.0,3.0,2'])

    def test_robots_txt(self):
        self.app.get('/robots.txt', status=200)

    def test_stats(self):
        self.app.get('/stats', status=200)

    def test_stats_location_json(self):
        app = self.app
        today = datetime.utcnow().date()
        yesterday = today - timedelta(1)
        yesterday = yesterday.strftime('%Y-%m-%d')
        session = self.db_slave_session
        stat = Stat(time=yesterday, value=2)
        stat.name = 'location'
        session.add(stat)
        session.commit()
        result = app.get('/stats_location.json', status=200)
        self.assertEqual(
            result.json, {'histogram': [
                {'num': 2, 'day': yesterday},
            ]}
        )

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
        for i in range(3):
            user = User(nickname=unicode(i))
            session.add(user)
            session.flush()
            score = Score(userid=user.id, value=i)
            session.add(score)
        session.commit()
        request = DummyRequest()
        request.db_slave_session = self.db_master_session
        inst = self._make_view(request)
        result = inst.leaders_view()
        self.assertEqual(
            result['leaders1'],
            [{'nickname': u'2', 'num': 2L}, {'nickname': u'1', 'num': 1L}])
        self.assertEqual(
            result['leaders2'],
            [{'nickname': u'0', 'num': 0L}])

    def test_stats(self):
        day = datetime.utcnow().date() - timedelta(1)
        session = self.db_master_session
        stats = [
            Stat(key=STAT_TYPE['location'], time=day, value=3),
            Stat(key=STAT_TYPE['cell'], time=day, value=2),
            Stat(key=STAT_TYPE['wifi'], time=day, value=2),
            Stat(key=STAT_TYPE['unique_cell'], time=day, value=1),
            Stat(key=STAT_TYPE['unique_wifi'], time=day, value=2),
        ]
        session.add_all(stats)
        session.commit()
        request = DummyRequest()
        request.db_slave_session = self.db_master_session
        inst = self._make_view(request)
        result = inst.stats_view()
        self.assertEqual(result['page_title'], 'Statistics')
        self.assertEqual(
            result['metrics'],
            [{'name': 'Locations', 'value': 3},
             {'name': 'Cells', 'value': 2},
             {'name': 'Unique Cells', 'value': 1},
             {'name': 'Wifi APs', 'value': 2},
             {'name': 'Unique Wifi APs', 'value': 2}])


class TestLayout(TestCase):

    def setUp(self):
        request = DummyRequest()
        self.config = setUp(request=request)

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
