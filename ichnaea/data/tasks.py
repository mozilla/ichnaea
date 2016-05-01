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


@celery_app.task(base=BaseTask, bind=True, queue='celery_reports',
                 _countdown=2, expires=20, _schedule=timedelta(seconds=32))
def update_incoming(self):
    export.IncomingQueue(self)(export_reports)


@celery_app.task(base=BaseTask, bind=True, queue='celery_export',
                 _countdown=1, expires=300)
def export_reports(self, name, queue_key):
    export.ReportExporter.export(self, name, queue_key)


@celery_app.task(base=BaseTask, bind=True, queue='celery_blue',
                 _countdown=5, expires=30, _schedule=timedelta(seconds=48),
                 _shard_model=models.BlueShard)
def update_blue(self, shard_id=None):
    station.BlueUpdater(self, shard_id=shard_id)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_cell',
                 _countdown=5, expires=30, _schedule=timedelta(seconds=41),
                 _shard_model=models.CellShard)
def update_cell(self, shard_id=None):
    station.CellUpdater(self, shard_id=shard_id)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_wifi',
                 _countdown=5, expires=30, _schedule=timedelta(seconds=40),
                 _shard_model=models.WifiShard)
def update_wifi(self, shard_id=None):
    station.WifiUpdater(self, shard_id=shard_id)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_cell',
                 _countdown=5, expires=30, _schedule=timedelta(seconds=44))
def update_cellarea(self):
    area.CellAreaUpdater(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_ocid',
                 _countdown=5, expires=30, _schedule=timedelta(seconds=45))
def update_cellarea_ocid(self):
    area.CellAreaOCIDUpdater(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_content',
                 _countdown=2, expires=30, _schedule=timedelta(seconds=47),
                 _shard_model=models.DataMap)
def update_datamap(self, shard_id=None):
    DataMapUpdater(self, shard_id=shard_id)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_content',
                 expires=18000, _schedule=timedelta(seconds=21600))
def update_statregion(self):
    stats.StatRegion(self)()


@celery_app.task(base=BaseTask, bind=True, queue='celery_content',
                 expires=2700, _schedule=crontab(minute=2))
def update_statcounter(self, ago=None):
    # BBB: ago argument
    stats.StatCounterUpdater(self)()
