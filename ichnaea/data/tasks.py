"""
Contains all celery tasks.

The task function names and this module's import path is used in generating
automatic statsd timer metrics to track the runtime of each task.
"""

from datetime import timedelta

from celery.schedules import crontab

from ichnaea.async.app import celery_app
from ichnaea.async.task import BaseTask
from ichnaea.data import area
from ichnaea.data.datamap import DataMapUpdater
from ichnaea.data import export
from ichnaea.data import monitor
from ichnaea.data import ocid
from ichnaea.data.score import ScoreUpdater
from ichnaea.data import station
from ichnaea.data import stats
from ichnaea import models


def _cell_export_enabled(app_config):
    return ('assets' in app_config.sections() and
            bool(app_config.get('assets', 'bucket', False)))


def _ocid_import_enabled(app_config):
    return 'import:ocid' in app_config.sections()


@celery_app.task(base=BaseTask, bind=True, queue='celery_ocid',
                 expires=2700, _schedule=crontab(minute=3),
                 _enabled=_cell_export_enabled)
def cell_export_diff(self, _bucket=None):
    ocid.CellExport(self)(hourly=True, _bucket=_bucket)


@celery_app.task(base=BaseTask, bind=True, queue='celery_ocid',
                 expires=39600, _schedule=crontab(hour=0, minute=13),
                 _enabled=_cell_export_enabled)
def cell_export_full(self, _bucket=None):
    ocid.CellExport(self)(hourly=False, _bucket=_bucket)


@celery_app.task(base=BaseTask, bind=True, queue='celery_ocid',
                 expires=2700, _schedule=crontab(minute=52),
                 _enabled=_ocid_import_enabled)
def cell_import_external(self):
    ocid.ImportExternal(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor',
                 expires=570, _schedule=timedelta(seconds=600))
def monitor_api_key_limits(self):
    monitor.ApiKeyLimits(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor',
                 expires=570, _schedule=timedelta(seconds=600))
def monitor_api_users(self):
    monitor.ApiUsers(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor',
                 expires=570, _schedule=timedelta(seconds=600),
                 _enabled=_ocid_import_enabled)
def monitor_ocid_import(self):
    monitor.OcidImport(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor',
                 expires=57, _schedule=timedelta(seconds=60))
def monitor_queue_size(self):
    monitor.QueueSize(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_export',
                 expires=10, _schedule=timedelta(seconds=6))
def schedule_export_reports(self):
    export.ExportScheduler(self)(export_reports)


@celery_app.task(base=BaseTask, bind=True, queue='celery_reports',
                 _countdown=2, expires=10, _schedule=timedelta(seconds=5))
def update_incoming(self):
    with self.redis_pipeline() as pipe:
        export.IncomingQueue(self, pipe)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_export',
                 _countdown=1, expires=300)
def export_reports(self, export_queue_key, queue_key=None):
    export.ReportExporter(
        self, export_queue_key, queue_key)(upload_reports)


@celery_app.task(base=BaseTask, bind=True, queue='celery_upload')
def upload_reports(self, export_queue_key, data, queue_key=None):
    export_queue = self.app.export_queues[export_queue_key]
    uploader_type = export_queue.uploader_type
    if uploader_type is not None:
        with self.redis_pipeline() as pipe:
            uploader_type(self, pipe, export_queue_key, queue_key)(data)


@celery_app.task(base=BaseTask, bind=True, queue='celery_blue',
                 _countdown=5, expires=30, _schedule=timedelta(seconds=18),
                 _shard_model=models.BlueShard)
def update_blue(self, shard_id=None):
    with self.redis_pipeline() as pipe:
        station.BlueUpdater(self, pipe, shard_id=shard_id)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_cell',
                 _countdown=5, expires=30, _schedule=timedelta(seconds=11),
                 _shard_model=models.CellShard)
def update_cell(self, shard_id=None):
    with self.redis_pipeline() as pipe:
        station.CellUpdater(self, pipe, shard_id=shard_id)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_wifi',
                 _countdown=5, expires=30, _schedule=timedelta(seconds=10),
                 _shard_model=models.WifiShard)
def update_wifi(self, shard_id=None):
    with self.redis_pipeline() as pipe:
        station.WifiUpdater(self, pipe, shard_id=shard_id)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_cell',
                 _countdown=5, expires=20, _schedule=timedelta(seconds=14))
def update_cellarea(self):
    area.CellAreaUpdater(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_ocid',
                 _countdown=5, expires=20, _schedule=timedelta(seconds=15))
def update_cellarea_ocid(self):
    area.CellAreaOCIDUpdater(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_content',
                 _countdown=2, expires=30, _schedule=timedelta(seconds=14),
                 _shard_model=models.DataMap)
def update_datamap(self, shard_id=None):
    with self.redis_pipeline() as pipe:
        DataMapUpdater(self, pipe, shard_id=shard_id)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_content',
                 _countdown=2, expires=10, _schedule=timedelta(seconds=9))
def update_score(self):
    with self.redis_pipeline() as pipe:
        ScoreUpdater(self, pipe)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_content',
                 expires=18000, _schedule=timedelta(seconds=21600))
def update_statregion(self):
    stats.StatRegion(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_content',
                 expires=2700, _schedule=crontab(minute=3))
def update_statcounter(self, ago=1):
    with self.redis_pipeline() as pipe:
        stats.StatCounterUpdater(self, pipe)(ago=ago)
