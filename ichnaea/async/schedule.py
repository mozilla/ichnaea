"""
Contains the `Celery Beat schedule
<http://celery.rtfd.org/en/latest/userguide/periodic-tasks.html>`_.
"""

from datetime import timedelta

from celery.schedules import crontab

from ichnaea.models import (
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
            'options': {'expires': 57},
        },
        'monitor-api-users': {
            'task': 'ichnaea.data.tasks.monitor_api_users',
            'schedule': timedelta(seconds=600),
            'options': {'expires': 570},
        },
        'monitor-api-key-limits': {
            'task': 'ichnaea.data.tasks.monitor_api_key_limits',
            'schedule': timedelta(seconds=600),
            'options': {'expires': 570},
        },

        # Statistics

        'update-statcounter': {
            'task': 'ichnaea.data.tasks.update_statcounter',
            'args': (1, ),
            'schedule': crontab(minute=3),
            'options': {'expires': 2700},
        },
        'update-statregion': {
            'task': 'ichnaea.data.tasks.update_statregion',
            'schedule': crontab(minute=5),
            'options': {'expires': 2700},
        },

        # Data Pipeline

        'schedule-export-reports': {
            'task': 'ichnaea.data.tasks.schedule_export_reports',
            'schedule': timedelta(seconds=8),
            'options': {'expires': 15},
        },

        'update-cell': {  # BBB
            'task': 'ichnaea.data.tasks.update_cell',
            'schedule': timedelta(seconds=57),
            'args': (500, ),
            'options': {'expires': 60},
        },

        'update-cellarea': {
            'task': 'ichnaea.data.tasks.update_cellarea',
            'schedule': timedelta(seconds=8),
            'args': (100, ),
            'options': {'expires': 15},
        },
        'update-cellarea-ocid': {
            'task': 'ichnaea.data.tasks.update_cellarea_ocid',
            'schedule': timedelta(seconds=9),
            'args': (100, ),
            'options': {'expires': 15},
        },

        'update-score': {
            'task': 'ichnaea.data.tasks.update_score',
            'args': (250, ),
            'schedule': timedelta(seconds=9),
            'options': {'expires': 10},
        },

    }

    for shard_id in CellShard.shards().keys():
        schedule.update({
            'update-cell-' + shard_id: {
                'task': 'ichnaea.data.tasks.update_cell',
                'schedule': timedelta(seconds=7),
                'args': (500, shard_id),
                'options': {'expires': 10},
            }
        })

    for shard_id in DataMap.shards().keys():
        schedule.update({
            'update-datamap-' + shard_id: {
                'task': 'ichnaea.data.tasks.update_datamap',
                'args': (500, shard_id),
                'schedule': timedelta(seconds=14),
                'options': {'expires': 20},
            },
        })

    for shard_id in WifiShard.shards().keys():
        schedule.update({
            'update-wifi-' + shard_id: {
                'task': 'ichnaea.data.tasks.update_wifi',
                'schedule': timedelta(seconds=6),
                'args': (500, shard_id),
                'options': {'expires': 10},
            }
        })

    if 'assets' in sections and app_config.get('assets', 'bucket', None):
        # only configure tasks if target bucket is configured
        schedule.update({
            'cell-export-full': {
                'task': 'ichnaea.data.tasks.cell_export_full',
                'schedule': crontab(hour=0, minute=13),
                'options': {'expires': 39600},
            },
            'cell-export-diff': {
                'task': 'ichnaea.data.tasks.cell_export_diff',
                'schedule': crontab(minute=3),
                'options': {'expires': 2700},
            },
        })

    if 'import:ocid' in sections:
        schedule.update({
            'monitor-ocid-import': {
                'task': 'ichnaea.data.tasks.monitor_ocid_import',
                'schedule': timedelta(seconds=600),
                'options': {'expires': 570},
            },
            'cell-import-external': {
                'task': 'ichnaea.data.tasks.cell_import_external',
                'args': (True, ),
                'schedule': crontab(minute=52),
                'options': {'expires': 2700},
            },

        })

    return schedule
