"""
Contains all celery tasks.

The task function names and this module's import path is used in generating
automatic statsd timer metrics to track the runtime of each task.
"""

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


@celery_app.task(base=BaseTask, bind=True, queue='celery_ocid',
                 expires=2700)
def cell_export_diff(self, _bucket=None):
    ocid.CellExport(self)(hourly=True, _bucket=_bucket)


@celery_app.task(base=BaseTask, bind=True, queue='celery_ocid',
                 expires=39600)
def cell_export_full(self, _bucket=None):
    ocid.CellExport(self)(hourly=False, _bucket=_bucket)


@celery_app.task(base=BaseTask, bind=True, queue='celery_ocid',
                 expires=2700)
def cell_import_external(self, diff=None):
    # BBB diff argument
    ocid.ImportExternal(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor',
                 expires=570)
def monitor_api_key_limits(self):
    monitor.ApiKeyLimits(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor',
                 expires=570)
def monitor_api_users(self):
    monitor.ApiUsers(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor',
                 expires=570)
def monitor_ocid_import(self):
    monitor.OcidImport(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor',
                 expires=57)
def monitor_queue_size(self):
    monitor.QueueSize(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_export',
                 expires=10)
def schedule_export_reports(self):
    export.ExportScheduler(self)(export_reports)


@celery_app.task(base=BaseTask, bind=True, queue='celery_reports',
                 countdown=2, expires=10)
def update_incoming(self, batch=None):
    # BBB batch argument
    with self.redis_pipeline() as pipe:
        export.IncomingQueue(self, pipe)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_export',
                 countdown=1, expires=300)
def export_reports(self, export_queue_key, queue_key=None):
    if not export_queue_key.startswith('queue_export_'):  # pragma: no cover
        # BBB
        export_queue_key = 'queue_export_' + 'queue_export_'

    export.ReportExporter(
        self, export_queue_key, queue_key)(upload_reports)


@celery_app.task(base=BaseTask, bind=True, queue='celery_upload')
def upload_reports(self, export_queue_key, data, queue_key=None):
    if not export_queue_key.startswith('queue_export_'):  # pragma: no cover
        # BBB
        export_queue_key = 'queue_export_' + export_queue_key

    export_queue = self.app.export_queues[export_queue_key]
    uploader_type = export_queue.uploader_type
    if uploader_type is not None:
        with self.redis_pipeline() as pipe:
            uploader_type(self, pipe, export_queue_key, queue_key)(data)


@celery_app.task(base=BaseTask, bind=True, queue='celery_blue',
                 countdown=5, expires=30)
def update_blue(self, batch=None, shard_id=None):
    # BBB batch argument
    with self.redis_pipeline() as pipe:
        station.BlueUpdater(self, pipe, shard_id=shard_id)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_cell',
                 countdown=5, expires=30)
def update_cell(self, batch=None, shard_id=None):
    # BBB batch argument
    with self.redis_pipeline() as pipe:
        station.CellUpdater(self, pipe, shard_id=shard_id)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_wifi',
                 countdown=5, expires=30)
def update_wifi(self, batch=None, shard_id=None):
    # BBB batch argument
    with self.redis_pipeline() as pipe:
        station.WifiUpdater(self, pipe, shard_id=shard_id)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_cell',
                 countdown=5, expires=20)
def update_cellarea(self, batch=None):
    # BBB batch argument
    area.CellAreaUpdater(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_ocid',
                 countdown=5, expires=20)
def update_cellarea_ocid(self, batch=None):
    # BBB batch argument
    area.CellAreaOCIDUpdater(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_content',
                 countdown=2, expires=30)
def update_datamap(self, batch=None, shard_id=None):
    # BBB batch argument
    with self.redis_pipeline() as pipe:
        DataMapUpdater(self, pipe, shard_id=shard_id)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_content',
                 countdown=2, expires=10)
def update_score(self, batch=None):
    # BBB batch argument
    with self.redis_pipeline() as pipe:
        ScoreUpdater(self, pipe)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_content',
                 expires=18000)
def update_statregion(self):
    stats.StatRegion(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_content',
                 expires=2700)
def update_statcounter(self, ago=1):
    with self.redis_pipeline() as pipe:
        stats.StatCounterUpdater(self, pipe)(ago=ago)
