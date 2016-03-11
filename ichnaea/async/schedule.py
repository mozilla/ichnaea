"""
Contains the `Celery Beat schedule
<http://celery.rtfd.org/en/latest/userguide/periodic-tasks.html>`_.
"""

from datetime import timedelta

from celery.schedules import crontab

from ichnaea.models import (
    BlueShard,
    CellShard,
    DataMap,
    WifiShard,
)


def celerybeat_schedule(app_config):
    """Return the celery beat schedule as a dictionary."""

    sections = app_config.sections()

    schedule = {

        # Monitoring

        'monitor-queue-size': {
            'task': 'ichnaea.data.tasks.monitor_queue_size',
            'schedule': timedelta(seconds=60),
        },
        'monitor-api-users': {
            'task': 'ichnaea.data.tasks.monitor_api_users',
            'schedule': timedelta(seconds=600),
        },
        'monitor-api-key-limits': {
            'task': 'ichnaea.data.tasks.monitor_api_key_limits',
            'schedule': timedelta(seconds=600),
        },

        # Statistics

        'update-statcounter': {
            'task': 'ichnaea.data.tasks.update_statcounter',
            'schedule': crontab(minute=3),
        },
        'update-statregion': {
            'task': 'ichnaea.data.tasks.update_statregion',
            'schedule': timedelta(seconds=3600 * 6),
        },

        # Data Pipeline

        'schedule-export-reports': {
            'task': 'ichnaea.data.tasks.schedule_export_reports',
            'schedule': timedelta(seconds=6),
        },
        'update-incoming': {
            'task': 'ichnaea.data.tasks.update_incoming',
            'schedule': timedelta(seconds=5),
        },

        'update-cellarea': {
            'task': 'ichnaea.data.tasks.update_cellarea',
            'schedule': timedelta(seconds=14),
        },
        'update-cellarea-ocid': {
            'task': 'ichnaea.data.tasks.update_cellarea_ocid',
            'schedule': timedelta(seconds=15),
        },

        'update-score': {
            'task': 'ichnaea.data.tasks.update_score',
            'schedule': timedelta(seconds=9),
        },

    }

    for shard_id in BlueShard.shards().keys():
        schedule.update({
            'update-blue-' + shard_id: {
                'task': 'ichnaea.data.tasks.update_blue',
                'schedule': timedelta(seconds=18),
                'kwargs': {'shard_id': shard_id},
            }
        })

    for shard_id in CellShard.shards().keys():
        schedule.update({
            'update-cell-' + shard_id: {
                'task': 'ichnaea.data.tasks.update_cell',
                'schedule': timedelta(seconds=11),
                'kwargs': {'shard_id': shard_id},
            }
        })

    for shard_id in DataMap.shards().keys():
        schedule.update({
            'update-datamap-' + shard_id: {
                'task': 'ichnaea.data.tasks.update_datamap',
                'schedule': timedelta(seconds=14),
                'kwargs': {'shard_id': shard_id},
            },
        })

    for shard_id in WifiShard.shards().keys():
        schedule.update({
            'update-wifi-' + shard_id: {
                'task': 'ichnaea.data.tasks.update_wifi',
                'schedule': timedelta(seconds=10),
                'kwargs': {'shard_id': shard_id},
            }
        })

    if 'assets' in sections and app_config.get('assets', 'bucket', None):
        # only configure tasks if target bucket is configured
        schedule.update({
            'cell-export-full': {
                'task': 'ichnaea.data.tasks.cell_export_full',
                'schedule': crontab(hour=0, minute=13),
            },
            'cell-export-diff': {
                'task': 'ichnaea.data.tasks.cell_export_diff',
                'schedule': crontab(minute=3),
            },
        })

    if 'import:ocid' in sections:
        schedule.update({
            'monitor-ocid-import': {
                'task': 'ichnaea.data.tasks.monitor_ocid_import',
                'schedule': timedelta(seconds=600),
            },
            'cell-import-external': {
                'task': 'ichnaea.data.tasks.cell_import_external',
                'schedule': crontab(minute=52),
            },

        })

    return schedule
