"""
Contains the `Celery Beat schedule
<http://celery.rtfd.org/en/latest/userguide/periodic-tasks.html>`_.
"""

from datetime import timedelta

from celery.schedules import crontab


CELERYBEAT_SCHEDULE = {

    # Monitoring tasks

    'monitor-queue-size': {
        'task': 'ichnaea.data.tasks.monitor_queue_size',
        'schedule': timedelta(seconds=60),
        'options': {'expires': 57},
    },
    'monitor-ocid-import': {
        'task': 'ichnaea.data.tasks.monitor_ocid_import',
        'schedule': timedelta(seconds=600),
        'options': {'expires': 570},
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

    # Daily

    'cell-export-full': {
        'task': 'ichnaea.data.tasks.cell_export_full',
        'schedule': crontab(hour=0, minute=13),
        'options': {'expires': 39600},
    },

    # Hourly

    'cell-export-diff': {
        'task': 'ichnaea.data.tasks.cell_export_diff',
        'schedule': crontab(minute=3),
        'options': {'expires': 2700},
    },
    'cell-import-external': {
        'task': 'ichnaea.data.tasks.cell_import_external',
        'args': (True, ),
        'schedule': crontab(minute=52),
        'options': {'expires': 2700},
    },
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

    # (less than) one minute

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

    'update-cell-gsm': {
        'task': 'ichnaea.data.tasks.update_cell',
        'schedule': timedelta(seconds=7),
        'args': (500, 'gsm'),
        'options': {'expires': 10},
    },
    'update-cell-wcdma': {
        'task': 'ichnaea.data.tasks.update_cell',
        'schedule': timedelta(seconds=7),
        'args': (500, 'wcdma'),
        'options': {'expires': 10},
    },
    'update-cell-lte': {
        'task': 'ichnaea.data.tasks.update_cell',
        'schedule': timedelta(seconds=7),
        'args': (500, 'lte'),
        'options': {'expires': 10},
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

    'update-datamap-ne': {
        'task': 'ichnaea.data.tasks.update_datamap',
        'args': (500, 'ne'),
        'schedule': timedelta(seconds=14),
        'options': {'expires': 20},
    },
    'update-datamap-nw': {
        'task': 'ichnaea.data.tasks.update_datamap',
        'args': (500, 'nw'),
        'schedule': timedelta(seconds=14),
        'options': {'expires': 20},
    },
    'update-datamap-se': {
        'task': 'ichnaea.data.tasks.update_datamap',
        'args': (500, 'se'),
        'schedule': timedelta(seconds=14),
        'options': {'expires': 20},
    },
    'update-datamap-sw': {
        'task': 'ichnaea.data.tasks.update_datamap',
        'args': (500, 'sw'),
        'schedule': timedelta(seconds=14),
        'options': {'expires': 20},
    },

    'update-score': {
        'task': 'ichnaea.data.tasks.update_score',
        'args': (250, ),
        'schedule': timedelta(seconds=9),
        'options': {'expires': 10},
    },

    'update-wifi-0': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (500, '0'),
        'options': {'expires': 10},
    },
    'update-wifi-1': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (500, '1'),
        'options': {'expires': 10},
    },
    'update-wifi-2': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (500, '2'),
        'options': {'expires': 10},
    },
    'update-wifi-3': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (500, '3'),
        'options': {'expires': 10},
    },
    'update-wifi-4': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (500, '4'),
        'options': {'expires': 10},
    },
    'update-wifi-5': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (500, '5'),
        'options': {'expires': 10},
    },
    'update-wifi-6': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (500, '6'),
        'options': {'expires': 10},
    },
    'update-wifi-7': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (500, '7'),
        'options': {'expires': 10},
    },
    'update-wifi-8': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (500, '8'),
        'options': {'expires': 10},
    },
    'update-wifi-9': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (500, '9'),
        'options': {'expires': 10},
    },
    'update-wifi-a': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (500, 'a'),
        'options': {'expires': 10},
    },
    'update-wifi-b': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (500, 'b'),
        'options': {'expires': 10},
    },
    'update-wifi-c': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (500, 'c'),
        'options': {'expires': 10},
    },
    'update-wifi-d': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (500, 'd'),
        'options': {'expires': 10},
    },
    'update-wifi-e': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (500, 'e'),
        'options': {'expires': 10},
    },
    'update-wifi-f': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (500, 'f'),
        'options': {'expires': 10},
    },

}  #:
