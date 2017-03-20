from inspect import getmembers
import os
import shutil
import tempfile

from celery import signals

from ichnaea.async.task import BaseTask


class TestBeat(object):

    def test_tasks(self, celery):
        tmpdir = tempfile.mkdtemp()
        filename = os.path.join(tmpdir, 'celerybeat-schedule')
        beat_app = celery.Beat()
        try:
            beat = beat_app.Service(
                app=celery, schedule_filename=filename)
            signals.beat_init.send(sender=beat)
            # parses the schedule as a side-effect
            scheduler = beat.get_scheduler()
            registered_tasks = set(scheduler._store['entries'].keys())
        finally:
            shutil.rmtree(tmpdir)

        # Import tasks after beat startup, to ensure beat_init
        # correctly loads configured Celery imports.
        from ichnaea.data import tasks
        all_tasks = set([m[1].shortname() for m in getmembers(tasks)
                         if isinstance(m[1], BaseTask)])

        assert (all_tasks - registered_tasks ==
                set(['data.update_blue', 'data.update_cell',
                     'data.update_datamap', 'data.update_wifi',
                     'data.cell_export_diff', 'data.cell_export_full',
                     'data.export_reports', 'data.update_statregion',
                     'data.update_statcounter',
                     ]))

        assert (set(['_'.join(name.split('_')[:-1]) for name in
                     registered_tasks - all_tasks]) ==
                set(['data.update_blue', 'data.update_cell',
                     'data.update_wifi']))

        for i in range(16):
            assert 'data.update_blue_%x' % i in registered_tasks
        for name in ('gsm', 'wcdma', 'lte'):
            assert 'data.update_cell_' + name in registered_tasks
        for i in range(16):
            assert 'data.update_wifi_%x' % i in registered_tasks


class TestWorkerConfig(object):

    def test_config(self, celery):
        assert celery.conf['task_always_eager']
        assert 'redis' in celery.conf['result_backend']
