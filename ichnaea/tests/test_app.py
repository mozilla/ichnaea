from unittest2 import TestCase
from webtest import TestApp
from ichnaea import application


class TestIchnaea(TestCase):

    def test_ok(self):
        app = TestApp(application)
        app.get('/', status=200)
