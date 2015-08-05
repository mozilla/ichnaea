"""
Contains the `Celery Beat schedule
<http://celery.rtfd.org/en/latest/userguide/periodic-tasks.html>`_.
"""

from datetime import timedelta

from celery.schedules import crontab


CELERYBEAT_SCHEDULE = {

    # Monitoring tasks

    'monitor-queue-length': {
        'task': 'ichnaea.data.tasks.monitor_queue_length',
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

    # Hourly

    'update-statcounter': {
        'task': 'ichnaea.data.tasks.update_statcounter',
        'args': (1, ),
        'schedule': crontab(minute=3),
    },
    'ocid-hourly-cell-delta-import': {
        'task': 'ichnaea.data.tasks.import_latest_ocid_cells',
        'args': (True, ),
        'schedule': crontab(minute=52),
        'options': {'expires': 2700},
    },
    's3-hourly-cell-delta-export': {
        'task': 'ichnaea.data.tasks.export_modified_cells',
        'args': (True, ),
        'schedule': crontab(minute=3),
        'options': {'expires': 2700},
    },
    's3-daily-cell-full-export': {
        'task': 'ichnaea.data.tasks.export_modified_cells',
        'args': (False, ),
        'schedule': crontab(hour=0, minute=13),
        'options': {'expires': 39600},
    },

    # Couple minutes

    'continuous-cell-scan-areas': {
        'task': 'ichnaea.data.tasks.scan_areas',
        'schedule': timedelta(seconds=121),
        'args': (500, ),
        'options': {'expires': 110},
    },

    # (less than) one minute

    'update-cell': {
        'task': 'ichnaea.data.tasks.update_cell',
        'schedule': timedelta(seconds=7),
        'args': (1000, ),
        'options': {'expires': 10},
    },
    'update-mapstat': {
        'task': 'ichnaea.data.tasks.update_mapstat',
        'args': (500, ),
        'schedule': timedelta(seconds=8),
        'options': {'expires': 10},
    },
    'update-score': {
        'task': 'ichnaea.data.tasks.update_score',
        'args': (500, ),
        'schedule': timedelta(seconds=9),
        'options': {'expires': 10},
    },
    'update-wifi': {
        'task': 'ichnaea.data.tasks.update_wifi',
        'schedule': timedelta(seconds=6),
        'args': (1000, ),
        'options': {'expires': 10},
    },

    'schedule-export-reports': {
        'task': 'ichnaea.data.tasks.schedule_export_reports',
        'schedule': timedelta(seconds=60),
        'options': {'expires': 57},
    },

}  #:
