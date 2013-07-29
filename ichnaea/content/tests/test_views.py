from datetime import datetime
from uuid import uuid4

from pyramid.testing import DummyRequest
from pyramid.testing import setUp
from pyramid.testing import tearDown
from unittest2 import TestCase
from webtest import TestApp

from ichnaea import main


def _make_app():
    wsgiapp = main({}, database='sqlite://')
    return TestApp(wsgiapp)


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

    def test_stats_empty(self):
        app = _make_app()
        request = DummyRequest()
        request.database = app.app.registry.database
        inst = self._make_view(request)
        result = inst.stats_view()
        self.assertEqual(result['page_title'], 'Statistics')
        self.assertEqual(result['total_measures'], 0)
        self.assertEqual(result['leaders'], [])

    def test_stats(self):
        app = _make_app()
        uid = uuid4().hex
        nickname = 'World Tr\xc3\xa4veler'
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0, "lon": 2.0, "wifi": [{"key": "a"}]},
                {"lat": 2.0, "lon": 3.0, "wifi": [{"key": "b"}]},
            ]},
            headers={'X-Token': uid, 'X-Nickname': nickname},
            status=204)
        request = DummyRequest()
        request.database = app.app.registry.database
        inst = self._make_view(request)
        result = inst.stats_view()
        self.assertEqual(result['page_title'], 'Statistics')
        self.assertEqual(result['total_measures'], 2)
        self.assertEqual(result['leaders'],
                         [{'nickname': nickname.decode('utf-8'),
                           'num': 2, 'token': uid[:8]}])


class TestFunctionalContent(TestCase):

    def test_favicon(self):
        app = _make_app()
        app.get('/favicon.ico', status=200)

    def test_homepage(self):
        app = _make_app()
        result = app.get('/', status=200)
        self.assertTrue('Strict-Transport-Security' in result.headers)

    def test_map(self):
        app = _make_app()
        app.get('/map', status=200)

    def test_map_csv(self):
        app = _make_app()
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0, "lon": 2.0, "wifi": [{"key": "a"}]},
                {"lat": 2.0, "lon": 3.0, "wifi": [{"key": "b"}]},
            ]},
            status=204)
        result = app.get('/map.csv', status=200)
        self.assertEqual(result.content_type, 'text/plain')
        text = result.text.replace('\r', '').strip('\n')
        text = text.split('\n')
        self.assertEqual(text, ['lat,lon', '1.0,2.0', '2.0,3.0'])

    def test_robots_txt(self):
        app = _make_app()
        app.get('/robots.txt', status=200)

    def test_stats(self):
        app = _make_app()
        app.get('/stats', status=200)

    def test_stats_json(self):
        app = _make_app()
        today = datetime.utcnow().date().strftime('%Y-%m-%d')
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0, "lon": 2.0, "time": today,
                 "wifi": [{"key": "a"}]},
            ]},
            status=204)
        result = app.get('/stats.json', status=200)
        self.assertEqual(
            result.json, {'histogram': [{'num': 1, 'day': today}]})


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
