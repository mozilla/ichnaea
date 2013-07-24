from unittest2 import TestCase
from webtest import TestApp
from ichnaea import application


class TestContentViews(TestCase):

    def test_homepage(self):
        app = TestApp(application)
        app.get('/', status=200)

    def test_map(self):
        app = TestApp(application)
        app.get('/map', status=200)

    def test_stats(self):
        app = TestApp(application)
        app.get('/stats', status=200)
