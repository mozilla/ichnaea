from datetime import datetime
from datetime import timedelta

from pyramid.testing import DummyRequest
from pyramid.testing import setUp
from pyramid.testing import tearDown
from unittest2 import TestCase

from ichnaea.db import (
    CellMeasure,
    Measure,
    WifiMeasure,
    Stat,
)
from ichnaea.tests.base import (
    AppTestCase,
    CeleryAppTestCase,
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

    def test_stats_json(self):
        app = self.app
        today = datetime.utcnow().date()
        yesterday = today - timedelta(1)
        yesterday = yesterday.strftime('%Y-%m-%d')
        session = self.db_slave_session
        stat = Stat(time=yesterday, value=2)
        stat.name = 'location'
        session.add(stat)
        session.commit()
        result = app.get('/stats.json', status=200)
        self.assertEqual(
            result.json, {'histogram': [
                {'num': 2, 'day': yesterday},
            ]}
        )


class TestStats(CeleryAppTestCase):

    def setUp(self):
        CeleryAppTestCase.setUp(self)
        request = DummyRequest()
        self.config = setUp(request=request)

    def tearDown(self):
        tearDown()
        CeleryAppTestCase.tearDown(self)

    def _make_view(self, request):
        from ichnaea.content.views import ContentViews
        return ContentViews(request)

    def test_stats(self):
        from ichnaea import tasks
        session = self.db_master_session
        session.add(Measure(lat=10000000, lon=20000000))
        session.add(Measure(lat=20000000, lon=30000000))
        session.add(Measure(lat=30000000, lon=40000000))
        session.add(CellMeasure(lat=10000000, lon=20000000, mcc=1))
        session.add(CellMeasure(lat=10000000, lon=20000000, mcc=1))
        session.add(WifiMeasure(lat=10000000, lon=20000000, key='a'))
        session.add(WifiMeasure(lat=10000000, lon=20000000, key='b'))
        session.commit()
        # run daily stats tasks
        task = tasks.histogram.delay(start=0, end=0)
        self.assertEqual(task.get(), 1)
        task = tasks.cell_histogram.delay(start=0, end=0)
        self.assertEqual(task.get(), 1)
        task = tasks.wifi_histogram.delay(start=0, end=0)
        self.assertEqual(task.get(), 1)
        task = tasks.unique_wifi_histogram.delay(ago=0)
        self.assertEqual(task.get(), 1)
        # check result
        request = DummyRequest()
        request.db_slave_session = self.db_master_session
        inst = self._make_view(request)
        result = inst.stats_view()
        self.assertEqual(result['page_title'], 'Statistics')
        self.assertEqual(result['leaders'], [])
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
