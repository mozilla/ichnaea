import os

from kombu import Queue
from kombu.serialization import register

from ichnaea.async.schedule import CELERYBEAT_SCHEDULE
from ichnaea.cache import redis_client
from ichnaea.config import read_config
from ichnaea import customjson
from ichnaea.db import Database
from ichnaea.log import (
    configure_raven,
    configure_stats,
)

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


def configure_celery(celery_app):
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

    celery_app.config_from_object('ichnaea.async.settings')
    celery_app.conf.update(
        BROKER_URL=broker_url,
        CELERY_RESULT_BACKEND=result_url,
        CELERY_QUEUES=CELERY_QUEUES,
        CELERYBEAT_SCHEDULE=CELERYBEAT_SCHEDULE,
    )
