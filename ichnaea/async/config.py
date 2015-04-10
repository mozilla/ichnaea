import os

from kombu import Queue
from kombu.serialization import register

from ichnaea.app_config import read_config
from ichnaea.async.schedule import CELERYBEAT_SCHEDULE
from ichnaea.cache import redis_client
from ichnaea import customjson
from ichnaea.db import Database
from ichnaea.logging import (
    configure_raven,
    configure_stats,
)

CELERY_IMPORTS = [
    'ichnaea.backup.tasks',
    'ichnaea.content.tasks',
    'ichnaea.data.tasks',
    'ichnaea.export.tasks',
    'ichnaea.monitor.tasks',
]

CELERY_QUEUES = (
    Queue('celery_default', routing_key='celery_default'),
    Queue('celery_export', routing_key='celery_export'),
    Queue('celery_incoming', routing_key='celery_incoming'),
    Queue('celery_insert', routing_key='celery_insert'),
    Queue('celery_monitor', routing_key='celery_monitor'),
    Queue('celery_reports', routing_key='celery_reports'),
    Queue('celery_upload', routing_key='celery_upload'),
)
CELERY_QUEUE_NAMES = frozenset([q.name for q in CELERY_QUEUES])


register('internal_json', customjson.kombu_dumps, customjson.kombu_loads,
         content_type='application/x-internaljson',
         content_encoding='utf-8')


def attach_database(app, settings=None, _db_rw=None):
    # called manually during tests
    if _db_rw is None:  # pragma: no cover
        db_rw = Database(settings['db_master'])
    else:
        db_rw = _db_rw
    app.db_rw = db_rw


def attach_raven_client(app, settings=None, _client=None):
    app.raven_client = _client
    if _client is None:  # pragma: no cover
        app.raven_client = configure_raven(settings.get('sentry_dsn'))


def attach_redis_client(app, settings=None, _client=None):
    app.redis_client = _client
    if _client is None:  # pragma: no cover
        app.redis_client = redis_client(settings.get('redis_url'))


def attach_stats_client(app, settings=None, _client=None):
    app.stats_client = _client
    if _client is None:  # pragma: no cover
        app.stats_client = configure_stats(settings.get('statsd_host'))


def configure_s3_backup(app, settings=None):
    # called manually during tests
    app.s3_settings = {
        'backup_bucket': settings['s3_backup_bucket'],
        'assets_bucket': settings['s3_assets_bucket'],
    }


def configure_ocid_import(app, settings=None):
    # called manually during tests
    app.ocid_settings = {
        'ocid_url': settings['ocid_url'],
        'ocid_apikey': settings['ocid_apikey'],
    }


def configure_celery(celery):
    conf = read_config()
    if conf.has_section('celery'):
        section = conf.get_map('celery')
    else:  # pragma: no cover
        # happens while building docs locally and on rtfd.org
        return

    # testing settings
    always_eager = bool(os.environ.get('CELERY_ALWAYS_EAGER', False))
    redis_uri = os.environ.get('REDIS_URI', 'redis://localhost:6379/1')

    if always_eager and redis_uri:
        broker_url = redis_uri
        result_url = redis_uri
    else:  # pragma: no cover
        broker_url = section['broker_url']
        result_url = section['result_url']

    if 'redis' in broker_url:
        broker_options = {}
        # Based on celery / redis caveats
        # celery.rtfd.org/en/latest/getting-started/brokers/redis.html#caveats
        broker_options['fanout_patterns'] = True
        broker_options['fanout_prefix'] = True
        broker_options['visibility_timeout'] = 3600

    if 'redis' in result_url:
        celery.conf.update(
            CELERY_RESULT_BACKEND=result_url,
        )

    celery.conf.update(
        # testing
        CELERY_ALWAYS_EAGER=always_eager,
        CELERY_EAGER_PROPAGATES_EXCEPTIONS=always_eager,
        # broker
        BROKER_URL=broker_url,
        BROKER_TRANSPORT_OPTIONS=broker_options,
        # queues
        CELERY_DEFAULT_QUEUE='celery_default',
        CELERY_QUEUES=CELERY_QUEUES,
        # tasks
        CELERY_IMPORTS=CELERY_IMPORTS,
        # optimization
        CELERYD_PREFETCH_MULTIPLIER=8,
        CELERY_DISABLE_RATE_LIMITS=True,
        CELERY_MESSAGE_COMPRESSION='gzip',
        # security
        CELERY_ACCEPT_CONTENT=['json', 'internal_json'],
        CELERY_RESULT_SERIALIZER='internal_json',
        CELERY_TASK_SERIALIZER='internal_json',
        # schedule
        CELERYBEAT_LOG_LEVEL="WARNING",
        CELERYBEAT_SCHEDULE=CELERYBEAT_SCHEDULE,
    )
