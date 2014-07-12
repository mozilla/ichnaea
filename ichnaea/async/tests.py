from unittest2 import TestCase

from ichnaea.async.config import attach_database
from ichnaea.worker import celery
from ichnaea.tests.base import DBTestCase


class TestWorkerConfig(TestCase):

    def test_config(self):
        self.assertTrue(celery.conf['CELERY_ALWAYS_EAGER'])
        self.assertEqual(celery.conf['CELERY_RESULT_BACKEND'], 'database')


class TestWorkerDatabase(DBTestCase):

    def setUp(self):
        super(TestWorkerDatabase, self).setUp()
        self._old_db = getattr(celery, 'db_master', None)

    def tearDown(self):
        if self._old_db:
            setattr(celery, 'db_master', self._old_db)
        else:
            delattr(celery, 'db_master')
        super(TestWorkerDatabase, self).tearDown()

    def test_attach(self):
        attach_database(celery, _db_master=self.db_master)
        self.assertTrue(hasattr(celery, 'db_master'))
