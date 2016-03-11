import os
import shutil
import tempfile

from ichnaea.async.app import celery_app
from ichnaea.async import schedule
from ichnaea.config import (
    DummyConfig,
    read_config,
)
from ichnaea.tests.base import CeleryTestCase, TestCase


class TestBeat(CeleryTestCase):

    def test_tasks(self):
        tmpdir = tempfile.mkdtemp()
        filename = os.path.join(tmpdir, 'celerybeat-schedule')
        beat_app = celery_app.Beat()
        app_config = read_config()
        try:
            beat = beat_app.Service(app=celery_app, schedule_filename=filename)
            # parses the schedule as a side-effect
            scheduler = beat.get_scheduler()
            registered_tasks = set(scheduler._store['entries'].keys())
            configured_tasks = set(schedule.celerybeat_schedule(app_config))
            self.assertEqual(registered_tasks, configured_tasks)
        finally:
            shutil.rmtree(tmpdir)

    def test_schedule(self):
        app_config = DummyConfig({
            'assets': {
                'bucket': 'bucket',
            },
            'export:internal': {
                'url': 'internal://',
                'batch': '1000',
            },
            'export:backup': {
                'url': 's3://bucket/directory/{api_key}/{year}/{month}/{day}',
                'skip_keys': 'test',
                'batch': '10000',
            },
            'export:outside': {
                'url': 'https://localhost:9/some/api/url?key=export',
                'skip_keys': 'test',
                'batch': '10000',
            },
            'import:ocid': {
                'url': 'https://localhost:9/downloads/',
                'apikey': 'some_key',
            },
        })

        tasks = set(schedule.celerybeat_schedule(app_config))
        for name in ('data.cell_export_full', 'data.cell_export_diff'):
            self.assertTrue(name in tasks)
        for name in ('data.cell_import_external', 'data.monitor_ocid_import'):
            self.assertTrue(name in tasks)
        for i in range(16):
            self.assertTrue('data.update_blue_%x' % i in tasks)
        for name in ('gsm', 'wcdma', 'lte'):
            self.assertTrue('data.update_cell_' + name in tasks)
        for name in ('ne', 'nw', 'se', 'sw'):
            self.assertTrue('data.update_datamap_' + name in tasks)
        for i in range(16):
            self.assertTrue('data.update_wifi_%x' % i in tasks)


class TestWorkerConfig(TestCase):

    def test_config(self):
        self.assertTrue(celery_app.conf['CELERY_ALWAYS_EAGER'])
        self.assertTrue('redis' in celery_app.conf['CELERY_RESULT_BACKEND'])
