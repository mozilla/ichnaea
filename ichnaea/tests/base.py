from unittest2 import TestCase

from webtest import TestApp

from ichnaea import main
from ichnaea.db import Database


def _make_db():
    return Database('sqlite://')


def _make_app():
    sqluri = 'sqlite://'
    wsgiapp = main({}, database=sqluri)
    return TestApp(wsgiapp)


class AppTestCase(TestCase):

    def setUp(self):
        self.app = _make_app()

    def tearDown(self):
        del self.app


class DBTestCase(TestCase):

    def setUp(self):
        self.db = _make_db()

    def tearDown(self):
        del self.db
