import os
from datetime import timedelta

from celery import Celery
from celery.app import app_or_default
from celery.signals import worker_process_init
from celery.schedules import crontab

from ichnaea import config
from ichnaea.db import Database
from ichnaea.heka_logging import configure_heka


CELERY_IMPORTS = [
    'ichnaea.tasks',
    'ichnaea.backup.tasks',
    'ichnaea.content.tasks',
    'ichnaea.backfill.tasks',
    'ichnaea.service.submit.tasks',
]

CELERYBEAT_SCHEDULE = {
    'histogram-cell-yesterday': {
        'task': 'ichnaea.content.tasks.cell_histogram',
        'schedule': crontab(hour=0, minute=3),
        'args': (1, ),
    },
    'histogram-wifi-yesterday': {
        'task': 'ichnaea.content.tasks.wifi_histogram',
        'schedule': crontab(hour=0, minute=3),
        'args': (1, ),
    },
    'histogram-unique-cell-yesterday': {
        'task': 'ichnaea.content.tasks.unique_cell_histogram',
        'schedule': crontab(hour=0, minute=4),
        'args': (1, ),
    },
    'histogram-unique-wifi-yesterday': {
        'task': 'ichnaea.content.tasks.unique_wifi_histogram',
        'schedule': crontab(hour=0, minute=4),
        'args': (1, ),
    },
    'continuous-cell-location-update': {
        'task': 'ichnaea.tasks.cell_location_update',
        'schedule': timedelta(seconds=299),  # 13*23
        'args': (10, 1000000, 1000),
        'options': {'expires': 290},
    },
    'continuous-cell-location-update-2': {
        'task': 'ichnaea.tasks.cell_location_update',
        'schedule': timedelta(seconds=319),  # 11*29
        'args': (1, 10, 5000),
        'options': {'expires': 310},
    },
    'continuous-wifi-location-update': {
        'task': 'ichnaea.tasks.wifi_location_update',
        'schedule': timedelta(seconds=323),  # 17*19
        'args': (10, 1000000, 1000),
        'options': {'expires': 320},
    },
    'continuous-wifi-location-update-2': {
        'task': 'ichnaea.tasks.wifi_location_update',
        'schedule': timedelta(seconds=329),  # 7*47
        'args': (1, 10, 5000),
        'options': {'expires': 320},
    },
    'continuous-cell-trim-excessive-data': {
        'task': 'ichnaea.tasks.cell_trim_excessive_data',
        'schedule': timedelta(seconds=21589),  # about 6 hours
        'args': (10000, 3, 1000),
        'options': {'expires': 21407},
    },
    'continuous-wifi-trim-excessive-data': {
        'task': 'ichnaea.tasks.wifi_trim_excessive_data',
        'schedule': timedelta(seconds=21577),  # about 6 hours
        'args': (10000, 3, 2000),
        'options': {'expires': 21407},
    },
    'continuous-cell-scan-lacs': {
        'task': 'ichnaea.tasks.scan_lacs',
        'schedule': timedelta(seconds=3607),  # about an hour
        'args': (1000, ),
        'options': {'expires': 3511},
    },

    # TODO: start scheduling this once we handled the backlog
    # 'backfill-celltower-info': {
    #     'task': 'ichnaea.backfill.tasks.do_backfill',
    #     'schedule': crontab(hour=0, minute=15),
    # }

    's3-schedule-cellmeasure-archival': {
        'task': 'ichnaea.backup.tasks.schedule_cellmeasure_archival',
        'args': (100, 1000000),
        'schedule': crontab(hour=0, minute=7),
        'options': {'expires': 43200},
    },
    's3-write-cellbackups': {
        'task': 'ichnaea.backup.tasks.write_cellmeasure_s3_backups',
        'args': (100, 10000, 300),
        'schedule': crontab(hour=1, minute=7),
        'options': {'expires': 43200},
    },

    's3-schedule-wifimeasures-archival': {
        'task': 'ichnaea.backup.tasks.schedule_wifimeasure_archival',
        'args': (100, 1000000),
        'schedule': crontab(hour=0, minute=17),
        'options': {'expires': 43200},
    },
    's3-write-wifibackups': {
        'task': 'ichnaea.backup.tasks.write_wifimeasure_s3_backups',
        'args': (100, 10000, 300),
        'schedule': crontab(hour=1, minute=17),
        'options': {'expires': 43200},
    },

    's3-delete-wifimeasures': {
        'task': 'ichnaea.backup.tasks.delete_wifimeasure_records',
        'args': (100, 3, 300),
        'schedule': crontab(hour=2, minute=27),
        'options': {'expires': 43200},
    },
    's3-delete-cellmeasures': {
        'task': 'ichnaea.backup.tasks.delete_cellmeasure_records',
        'args': (100, 3, 300),
        'schedule': crontab(hour=2, minute=27),
        'options': {'expires': 43200},
    },

}

celery = Celery('ichnaea.worker')


def attach_database(app, settings=None, _db_master=None):
    # called manually during tests
    if _db_master is None:  # pragma: no cover
        db_master = Database(settings['db_master'])
    else:
        db_master = _db_master
    app.db_master = db_master


def configure_s3_backup(app, settings=None):
    # called manually during tests
    app.s3_settings = {
        'backup_bucket': settings['s3_backup_bucket'],
        'backup_prefix': settings['s3_backup_prefix'],
    }


@worker_process_init.connect
def init_worker_process(signal, sender, **kw):  # pragma: no cover
    # called automatically when `celery worker` is started
    # get the app in the current worker process
    app = app_or_default()
    settings = config().get_map('ichnaea')
    attach_database(app, settings=settings)
    configure_s3_backup(app, settings=settings)
    configure_heka()


def configure(celery=celery):
    conf = config()
    if conf.has_section('celery'):
        section = conf.get_map('celery')
    else:  # pragma: no cover
        # happens while building docs locally and on rtfd.org
        return

    database_options = {
        "pool_recycle": 3600,
        "pool_size": 10,
        "pool_timeout": 10,
        "isolation_level": "READ COMMITTED",
    }

    # testing overrides
    sqluri = os.environ.get('SQLURI', '')

    if sqluri:
        broker_url = sqluri
        result_url = sqluri
    else:  # pragma: no cover
        broker_url = section['broker_url']
        result_url = section['result_url']

    if 'pymysql' in broker_url:
        broker_url = 'sqla+' + broker_url

    if 'pymysql' in broker_url:
        broker_connect_args = {"charset": "utf8"}
        broker_options = database_options.copy()
        broker_options['connect_args'] = broker_connect_args
    elif 'redis' in broker_url:
        broker_options = {}
        # Based on celery / redis caveats
        # celery.rtfd.org/en/latest/getting-started/brokers/redis.html#caveats
        broker_options['fanout_patterns'] = True
        broker_options['fanout_prefix'] = True
        broker_options['visibility_timeout'] = 3600

    if 'pymysql' in result_url:
        result_connect_args = {"charset": "utf8"}
        result_options = database_options.copy()
        result_options['connect_args'] = result_connect_args
        celery.conf.update(
            CELERY_RESULT_BACKEND='database',
            CELERY_RESULT_DBURI=result_url,
            CELERY_RESULT_ENGINE_OPTIONS=result_options,
        )
    elif 'redis' in result_url:
        celery.conf.update(
            CELERY_RESULT_BACKEND=result_url,
        )

    # testing setting
    always_eager = bool(os.environ.get('CELERY_ALWAYS_EAGER', False))

    celery.conf.update(
        # testing
        CELERY_ALWAYS_EAGER=always_eager,
        CELERY_EAGER_PROPAGATES_EXCEPTIONS=always_eager,
        # broker
        BROKER_URL=broker_url,
        BROKER_TRANSPORT_OPTIONS=broker_options,
        # tasks
        CELERY_IMPORTS=CELERY_IMPORTS,
        # forward compatibility
        CELERYD_FORCE_EXECV=True,
        # optimization
        CELERYD_PREFETCH_MULTIPLIER=8,
        CELERY_DISABLE_RATE_LIMITS=True,
        CELERY_MESSAGE_COMPRESSION='gzip',
        # security
        CELERY_ACCEPT_CONTENT=['json'],
        CELERY_RESULT_SERIALIZER='json',
        CELERY_TASK_SERIALIZER='json',
        # schedule
        CELERYBEAT_LOG_LEVEL="WARNING",
        CELERYBEAT_SCHEDULE=CELERYBEAT_SCHEDULE,
    )

configure(celery)
