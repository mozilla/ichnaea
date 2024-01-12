"""
Contains all celery tasks.

The task function names and this module's import path is used in generating
automatic statsd timer metrics to track the runtime of each task.
"""

from datetime import timedelta

from celery.schedules import crontab

from ichnaea import models
from ichnaea.data import (
    _cell_export_enabled,
    _map_content_enabled,
    area,
    datamap,
    export,
    monitor,
    public,
    station,
    stats,
)
from ichnaea.taskapp.app import celery_app
from ichnaea.taskapp.task import BaseTask


@celery_app.task(
    base=BaseTask,
    bind=True,
    queue="celery_export",
    expires=2700,
    _schedule=crontab(minute=3),
    _enabled=_cell_export_enabled,
)
def cell_export_diff(self, _bucket=None):
    public.CellExport(self)(hourly=True, _bucket=_bucket)


@celery_app.task(
    base=BaseTask,
    bind=True,
    queue="celery_export",
    expires=39600,
    _schedule=crontab(hour=0, minute=37),
    _enabled=_cell_export_enabled,
)
def cell_export_full(self, _bucket=None):
    public.CellExport(self)(hourly=False, _bucket=_bucket)


@celery_app.task(
    base=BaseTask,
    bind=True,
    queue="celery_monitor",
    expires=570,
    _schedule=timedelta(seconds=600),
)
def monitor_api_key_limits(self):
    monitor.ApiKeyLimits(self)()


@celery_app.task(
    base=BaseTask,
    bind=True,
    queue="celery_monitor",
    expires=570,
    _schedule=timedelta(seconds=600),
)
def monitor_api_users(self):
    monitor.ApiUsers(self)()


@celery_app.task(
    base=BaseTask,
    bind=True,
    queue="celery_monitor",
    expires=57,
    _schedule=timedelta(seconds=60),
)
def monitor_queue_size_and_rate_control(self):
    monitor.QueueSizeAndRateControl(self)()


@celery_app.task(base=BaseTask, bind=True, queue="celery_monitor")
def sentry_test(self, msg):
    self.app.raven_client.captureMessage(msg)


@celery_app.task(
    base=BaseTask,
    bind=True,
    queue="celery_reports",
    _countdown=2,
    expires=20,
    _schedule=timedelta(seconds=32),
)
def update_incoming(self):
    export.IncomingQueue(self)(export_reports)


@celery_app.task(
    base=BaseTask, bind=True, queue="celery_export", expires=300
)
def export_reports(self, name, queue_key):
    export.ReportExporter.export(self, name, queue_key)


@celery_app.task(
    base=BaseTask,
    bind=True,
    queue="celery_blue",
    expires=30,
    _schedule=timedelta(seconds=48),
    _shard_model=models.BlueShard,
)
def update_blue(self, shard_id=None):
    station.BlueUpdater(self, shard_id=shard_id)()


@celery_app.task(
    base=BaseTask,
    bind=True,
    queue="celery_cell",
    expires=30,
    _schedule=timedelta(seconds=41),
    _shard_model=models.CellShard,
)
def update_cell(self, shard_id=None):
    station.CellUpdater(self, shard_id=shard_id)()


@celery_app.task(
    base=BaseTask,
    bind=True,
    queue="celery_wifi",
    expires=30,
    _schedule=timedelta(seconds=40),
    _shard_model=models.WifiShard,
)
def update_wifi(self, shard_id=None):
    station.WifiUpdater(self, shard_id=shard_id)()


@celery_app.task(
    base=BaseTask,
    bind=True,
    queue="celery_cell",
    expires=30,
    _schedule=timedelta(seconds=44),
)
def update_cellarea(self):
    area.CellAreaUpdater(self)()


@celery_app.task(
    base=BaseTask,
    bind=True,
    queue="celery_content",
    expires=18000,
    _schedule=crontab(hour=0, minute=17),
    _shard_model=models.DataMap,
    _enabled=_map_content_enabled,
)
def cleanup_datamap(self, shard_id=None):
    datamap.DataMapCleaner(self, shard_id=shard_id)()


@celery_app.task(
    base=BaseTask,
    bind=True,
    queue="celery_content",
    _countdown=2,
    expires=30,
    _schedule=timedelta(seconds=47),
    _shard_model=models.DataMap,
    _enabled=_map_content_enabled,
)
def update_datamap(self, shard_id=None):
    datamap.DataMapUpdater(self, shard_id=shard_id)()


@celery_app.task(
    base=BaseTask,
    bind=True,
    queue="celery_content",
    expires=18000,
    _schedule=crontab(hour=0, minute=7),
    _enabled=_map_content_enabled,
)
def update_statregion(self):
    stats.StatRegion(self)()


@celery_app.task(
    base=BaseTask,
    bind=True,
    queue="celery_content",
    expires=18000,
    _schedule=crontab(hour=0, minute=23),
)
def cleanup_stat(self):
    stats.StatCleaner(self)()


@celery_app.task(
    base=BaseTask,
    bind=True,
    queue="celery_content",
    expires=570,
    _schedule=timedelta(seconds=600),
)
def update_statcounter(self):
    stats.StatCounterUpdater(self)()
