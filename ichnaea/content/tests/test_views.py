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

    def test_stats(self):
        app = _make_app()
        request = DummyRequest()
        request.database = app.app.registry.database
        inst = self._make_view(request)
        result = inst.stats_view()
        self.assertEqual(result['page_title'], 'Statistics')
        self.assertEqual(result['total_measures'], 0)
        self.assertEqual(result['leaders'], [])


class TestFunctionalContentViews(TestCase):

    def test_homepage(self):
        app = _make_app()
        app.get('/', status=200)

    def test_map(self):
        app = _make_app()
        app.get('/map', status=200)

    def test_stats(self):
        app = _make_app()
        app.get('/stats', status=200)
