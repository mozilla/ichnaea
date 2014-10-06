from datetime import timedelta

from celery.schedules import crontab


CELERYBEAT_SCHEDULE = {

    # Monitoring tasks

    'monitor-queue-length': {
        'task': 'ichnaea.monitor.tasks.monitor_queue_length',
        'schedule': timedelta(seconds=60),
        'options': {'expires': 57},
    },
    'monitor-api-key-limits': {
        'task': 'ichnaea.monitor.tasks.monitor_api_key_limits',
        'schedule': timedelta(seconds=600),
        'options': {'expires': 570},
    },

    # Continuous location update tasks

    'location-update-cell-1': {
        'task': 'ichnaea.data.tasks.location_update_cell',
        'schedule': timedelta(seconds=299),  # 13*23
        'args': (1, 10, 5000),
        'options': {'expires': 290},
    },
    'location-update-cell-10': {
        'task': 'ichnaea.data.tasks.location_update_cell',
        'schedule': timedelta(seconds=305),  # 5*61
        'args': (10, 1000, 1000),
        'options': {'expires': 295},
    },
    'location-update-cell-1000': {
        'task': 'ichnaea.data.tasks.location_update_cell',
        'schedule': timedelta(seconds=323),  # 17*19
        'args': (1000, 1000000, 100),
        'options': {'expires': 310},
    },
    'location-update-wifi-1': {
        'task': 'ichnaea.data.tasks.location_update_wifi',
        'schedule': timedelta(seconds=301),  # 7*43
        'args': (1, 10, 5000),
        'options': {'expires': 290},
    },
    'location-update-wifi-10': {
        'task': 'ichnaea.data.tasks.location_update_wifi',
        'schedule': timedelta(seconds=319),  # 11*29
        'args': (10, 1000, 1000),
        'options': {'expires': 310},
    },
    'location-update-wifi-1000': {
        'task': 'ichnaea.data.tasks.location_update_wifi',
        'schedule': timedelta(seconds=329),  # 7*47
        'args': (1000, 1000000, 100),
        'options': {'expires': 320},
    },
    'continuous-cell-scan-lacs': {
        'task': 'ichnaea.data.tasks.scan_lacs',
        'schedule': timedelta(seconds=3607),  # about an hour
        'args': (1000, ),
        'options': {'expires': 3511},
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

    's3-schedule-cellmeasure-archival': {
        'task': 'ichnaea.backup.tasks.schedule_cellmeasure_archival',
        'args': (100, 1000000),
        'schedule': crontab(hour=1, minute=7),
        'options': {'expires': 43200},
    },
    's3-write-cellbackups': {
        'task': 'ichnaea.backup.tasks.write_cellmeasure_s3_backups',
        'args': (100, 10000, 300),
        'schedule': crontab(hour=2, minute=7),
        'options': {'expires': 43200},
    },
    's3-schedule-wifimeasures-archival': {
        'task': 'ichnaea.backup.tasks.schedule_wifimeasure_archival',
        'args': (100, 1000000),
        'schedule': crontab(hour=1, minute=17),
        'options': {'expires': 43200},
    },
    's3-write-wifibackups': {
        'task': 'ichnaea.backup.tasks.write_wifimeasure_s3_backups',
        'args': (100, 10000, 300),
        'schedule': crontab(hour=2, minute=17),
        'options': {'expires': 43200},
    },
    's3-delete-wifimeasures': {
        'task': 'ichnaea.backup.tasks.delete_wifimeasure_records',
        'args': (100, 2, 300),
        'schedule': crontab(hour=3, minute=17),
        'options': {'expires': 43200},
    },
    's3-delete-cellmeasures': {
        'task': 'ichnaea.backup.tasks.delete_cellmeasure_records',
        'args': (100, 2, 300),
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

    'nightly-cell-unthrottle-messages': {
        'task': 'ichnaea.backup.tasks.cell_unthrottle_measures',
        'schedule': crontab(hour=3, minute=17),
        'args': (10000, 1000),
        'options': {'expires': 43200},
    },
    'nightly-wifi-unthrottle-messages': {
        'task': 'ichnaea.backup.tasks.wifi_unthrottle_measures',
        'schedule': crontab(hour=3, minute=27),
        'args': (10000, 1000),
        'options': {'expires': 43200},
    },

}
