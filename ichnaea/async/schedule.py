from datetime import timedelta

from celery.schedules import crontab


CELERYBEAT_SCHEDULE = {

    # Monitoring tasks

    'monitor-queue-length': {
        'task': 'ichnaea.monitor.tasks.monitor_queue_length',
        'schedule': timedelta(seconds=60),
        'options': {'expires': 57},
    },
    'monitor-observations': {
        'task': 'ichnaea.monitor.tasks.monitor_measures',
        'schedule': timedelta(seconds=900),
        'options': {'expires': 990},
    },
    'monitor-ocid-import': {
        'task': 'ichnaea.monitor.tasks.monitor_ocid_import',
        'schedule': timedelta(seconds=600),
        'options': {'expires': 570},
    },
    'monitor-api-key-limits': {
        'task': 'ichnaea.monitor.tasks.monitor_api_key_limits',
        'schedule': timedelta(seconds=600),
        'options': {'expires': 570},
    },

    # Continuous location update tasks

    'location-update-cell-1': {
        'task': 'ichnaea.data.tasks.location_update_cell',
        'schedule': timedelta(seconds=29),
        'args': (1, 10, 4000),
        'options': {'expires': 25},
    },
    'location-update-cell-10': {
        'task': 'ichnaea.data.tasks.location_update_cell',
        'schedule': timedelta(seconds=149),
        'args': (10, 1000, 1000),
        'options': {'expires': 120},
    },
    'location-update-cell-1000': {
        'task': 'ichnaea.data.tasks.location_update_cell',
        'schedule': timedelta(seconds=311),
        'args': (1000, 1000000, 100),
        'options': {'expires': 300},
    },
    'location-update-wifi-1': {
        'task': 'ichnaea.data.tasks.location_update_wifi',
        'schedule': timedelta(seconds=31),
        'args': (1, 10, 4000),
        'options': {'expires': 25},
    },
    'location-update-wifi-10': {
        'task': 'ichnaea.data.tasks.location_update_wifi',
        'schedule': timedelta(seconds=151),
        'args': (10, 1000, 1000),
        'options': {'expires': 120},
    },
    'location-update-wifi-1000': {
        'task': 'ichnaea.data.tasks.location_update_wifi',
        'schedule': timedelta(seconds=313),
        'args': (1000, 1000000, 100),
        'options': {'expires': 300},
    },
    'continuous-cell-scan-areas': {
        'task': 'ichnaea.data.tasks.scan_areas',
        'schedule': timedelta(seconds=331),
        'args': (500, ),
        'options': {'expires': 300},
    },

    # Daily content tasks

    'histogram-cell-yesterday': {
        'task': 'ichnaea.content.tasks.cell_histogram',
        'schedule': crontab(hour=0, minute=3),
        'args': (1, ),
    },
    'histogram-wifi-yesterday': {
        'task': 'ichnaea.content.tasks.wifi_histogram',
        'schedule': crontab(hour=0, minute=4),
        'args': (1, ),
    },
    'histogram-unique-cell-yesterday': {
        'task': 'ichnaea.content.tasks.unique_cell_histogram',
        'schedule': crontab(hour=0, minute=5),
        'args': (1, ),
    },
    'histogram-unique-ocid-cell-yesterday': {
        'task': 'ichnaea.content.tasks.unique_ocid_cell_histogram',
        'schedule': crontab(hour=0, minute=6),
        'args': (1, ),
    },
    'histogram-unique-wifi-yesterday': {
        'task': 'ichnaea.content.tasks.unique_wifi_histogram',
        'schedule': crontab(hour=0, minute=7),
        'args': (1, ),
    },

    # Daily backup tasks

    's3-schedule-cellobservation-archival': {
        'task': 'ichnaea.backup.tasks.schedule_cellmeasure_archival',
        'args': (1000, 100000),
        'schedule': crontab(hour=1, minute=7),
        'options': {'expires': 43200},
    },
    's3-write-cellbackups': {
        'task': 'ichnaea.backup.tasks.write_cellmeasure_s3_backups',
        'args': (1000, 10000, 60),
        'schedule': crontab(hour=2, minute=7),
        'options': {'expires': 43200},
    },
    's3-schedule-wifiobservations-archival': {
        'task': 'ichnaea.backup.tasks.schedule_wifimeasure_archival',
        'args': (1000, 100000),
        'schedule': crontab(hour=1, minute=17),
        'options': {'expires': 43200},
    },
    's3-write-wifibackups': {
        'task': 'ichnaea.backup.tasks.write_wifimeasure_s3_backups',
        'args': (1000, 10000, 60),
        'schedule': crontab(hour=2, minute=17),
        'options': {'expires': 43200},
    },
    's3-delete-wifiobservations': {
        'task': 'ichnaea.backup.tasks.delete_wifimeasure_records',
        'args': (1000, 1, 60, 10000),
        'schedule': crontab(hour=3, minute=17),
        'options': {'expires': 43200},
    },
    's3-delete-cellobservations': {
        'task': 'ichnaea.backup.tasks.delete_cellmeasure_records',
        'args': (1000, 1, 60, 10000),
        'schedule': crontab(hour=3, minute=27),
        'options': {'expires': 43200},
    },

    # OCID cell import task

    'ocid-hourly-cell-delta-import': {
        'task': 'ichnaea.export.tasks.import_latest_ocid_cells',
        'args': (True, ),
        'schedule': crontab(minute=52),
        'options': {'expires': 2700},
    },

    # Cell export tasks

    's3-hourly-cell-delta-export': {
        'task': 'ichnaea.export.tasks.export_modified_cells',
        'args': (True, ),
        'schedule': crontab(minute=3),
        'options': {'expires': 2700},
    },
    's3-daily-cell-full-export': {
        'task': 'ichnaea.export.tasks.export_modified_cells',
        'args': (False, ),
        'schedule': crontab(hour=0, minute=13),
        'options': {'expires': 39600},
    },

}
