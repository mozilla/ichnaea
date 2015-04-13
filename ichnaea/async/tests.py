import os
import shutil
import tempfile
from unittest2 import TestCase

from ichnaea.async.app import celery_app
from ichnaea.async import schedule
from ichnaea.tests.base import CeleryTestCase


class TestBeat(CeleryTestCase):

    def test_schedule(self):
        tmpdir = tempfile.mkdtemp()
        filename = os.path.join(tmpdir, 'celerybeat-schedule')
        beat_app = celery_app.Beat()
        try:
            beat = beat_app.Service(app=celery_app, schedule_filename=filename)
            # parses the schedule as a side-effect
            scheduler = beat.get_scheduler()
            registered_tasks = set(scheduler._store['entries'].keys())
            configured_tasks = set(schedule.CELERYBEAT_SCHEDULE)
            self.assertEqual(registered_tasks, configured_tasks)
        finally:
            shutil.rmtree(tmpdir)


class TestWorkerConfig(TestCase):

    def test_config(self):
        self.assertTrue(celery_app.conf['CELERY_ALWAYS_EAGER'])
        self.assertTrue('redis' in celery_app.conf['CELERY_RESULT_BACKEND'])
