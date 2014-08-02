import os
import shutil
import tempfile
from unittest2 import TestCase

from ichnaea.async.config import attach_database
from ichnaea.async import schedule
from ichnaea.worker import celery
from ichnaea.tests.base import (
    CeleryTestCase,
    DBTestCase,
)


class TestBeat(CeleryTestCase):

    def test_schedule(self):
        tmpdir = tempfile.mkdtemp()
        filename = os.path.join(tmpdir, 'celerybeat-schedule')
        beat_app = celery.Beat()
        try:
            beat = beat_app.Service(app=celery, schedule_filename=filename)
            # parses the schedule as a side-effect
            scheduler = beat.get_scheduler()
            registered_tasks = set(scheduler._store['entries'].keys())
            configured_tasks = set(schedule.CELERYBEAT_SCHEDULE)
            # add the internal celery task
            configured_tasks.add('celery.backend_cleanup')
            self.assertEqual(registered_tasks, configured_tasks)
        finally:
            shutil.rmtree(tmpdir)


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
