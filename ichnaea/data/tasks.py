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


@celery_app.task(base=BaseTask, bind=True, queue='celery_ocid')
def cell_export_diff(self, _bucket=None):
    ocid.CellExport(self)(hourly=True, _bucket=_bucket)


@celery_app.task(base=BaseTask, bind=True, queue='celery_ocid')
def cell_export_full(self, _bucket=None):
    ocid.CellExport(self)(hourly=False, _bucket=_bucket)


@celery_app.task(base=BaseTask, bind=True, queue='celery_ocid')
def cell_import_external(self, diff=True):
    ocid.ImportExternal(self)(diff=diff)


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor')
def monitor_api_key_limits(self):
    monitor.ApiKeyLimits(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor')
def monitor_api_users(self):
    monitor.ApiUsers(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor')
def monitor_ocid_import(self):
    monitor.OcidImport(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor')
def monitor_queue_size(self):
    monitor.QueueSize(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_export')
def schedule_export_reports(self):
    export.ExportScheduler(self)(export_reports)


@celery_app.task(base=BaseTask, bind=True, queue='celery_reports')
def update_incoming(self, batch=100):
    with self.redis_pipeline() as pipe:
        export.IncomingQueue(self, pipe)(batch=batch)


@celery_app.task(base=BaseTask, bind=True, queue='celery_export')
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


@celery_app.task(base=BaseTask, bind=True, queue='celery_blue')
def update_blue(self, batch=1000, shard_id=None):
    with self.redis_pipeline() as pipe:
        station.BlueUpdater(self, pipe, shard_id=shard_id)(batch=batch)


@celery_app.task(base=BaseTask, bind=True, queue='celery_cell')
def update_cell(self, batch=1000, shard_id=None):
    with self.redis_pipeline() as pipe:
        station.CellUpdater(self, pipe, shard_id=shard_id)(batch=batch)


@celery_app.task(base=BaseTask, bind=True, queue='celery_wifi')
def update_wifi(self, batch=1000, shard_id=None):
    with self.redis_pipeline() as pipe:
        station.WifiUpdater(self, pipe, shard_id=shard_id)(batch=batch)


@celery_app.task(base=BaseTask, bind=True, queue='celery_cell')
def update_cellarea(self, batch=100):
    area.CellAreaUpdater(self)(batch=batch)


@celery_app.task(base=BaseTask, bind=True, queue='celery_ocid')
def update_cellarea_ocid(self, batch=100):
    area.CellAreaOCIDUpdater(self)(batch=batch)


@celery_app.task(base=BaseTask, bind=True, queue='celery_content')
def update_datamap(self, batch=1000, shard_id=None):
    with self.redis_pipeline() as pipe:
        DataMapUpdater(self, pipe, shard_id=shard_id)(batch=batch)


@celery_app.task(base=BaseTask, bind=True, queue='celery_content')
def update_score(self, batch=1000):
    with self.redis_pipeline() as pipe:
        ScoreUpdater(self, pipe)(batch=batch)


@celery_app.task(base=BaseTask, bind=True, queue='celery_content')
def update_statregion(self):
    stats.StatRegion(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_content')
def update_statcounter(self, ago=1):
    with self.redis_pipeline() as pipe:
        stats.StatCounterUpdater(self, pipe)(ago=ago)
