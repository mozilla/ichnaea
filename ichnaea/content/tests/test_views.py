from unittest2 import TestCase
from webtest import TestApp

from ichnaea import main


def _make_app():
    wsgiapp = main({}, database='sqlite://')
    return TestApp(wsgiapp)


class TestContentViews(TestCase):

    def test_homepage(self):
        app = _make_app()
        app.get('/', status=200)

    def test_map(self):
        app = _make_app()
        app.get('/map', status=200)

    def test_stats(self):
        app = _make_app()
        app.get('/stats', status=200)
