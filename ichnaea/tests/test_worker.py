from unittest2 import TestCase

from ichnaea.worker import attach_database
from ichnaea.worker import celery
from ichnaea.tests.base import DBTestCase


class TestWorkerConfig(TestCase):

    def test_config(self):
        self.assertTrue(celery.conf['CELERY_ALWAYS_EAGER'])
        self.assertEqual(celery.conf['CELERY_RESULT_BACKEND'], 'database')


class TestWorkerDatabase(DBTestCase):

    def setUp(self):
        super(TestWorkerDatabase, self).setUp()
        self._old_db_a = getattr(celery, 'archival_db', None)
        self._old_db_v = getattr(celery, 'volatile_db', None)

    def tearDown(self):
        if self._old_db_a:
            setattr(celery, 'archival_db', self._old_db_a)
        else:
            delattr(celery, 'archival_db')
        if self._old_db_v:
            setattr(celery, 'volatile_db', self._old_db_v)
        else:
            delattr(celery, 'volatile_db')
        super(TestWorkerDatabase, self).tearDown()

    def test_attach(self):
        attach_database(celery,
                        _archival_db=self.archival_db,
                        _volatile_db=self.volatile_db)
        self.assertTrue(hasattr(celery, 'archival_db'))
        self.assertTrue(hasattr(celery, 'volatile_db'))
