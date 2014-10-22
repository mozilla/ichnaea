import os

from kombu import Queue

from ichnaea.app_config import read_config
from ichnaea.async.schedule import CELERYBEAT_SCHEDULE
from ichnaea.cache import redis_client
from ichnaea.db import Database


CELERY_IMPORTS = [
    'ichnaea.backfill.tasks',
    'ichnaea.backup.tasks',
    'ichnaea.content.tasks',
    'ichnaea.data.tasks',
    'ichnaea.export.tasks',
    'ichnaea.monitor.tasks',
]

CELERY_QUEUES = (
    Queue('default', routing_key='default'),
    Queue('incoming', routing_key='incoming'),
    Queue('insert', routing_key='insert'),
    Queue('monitor', routing_key='monitor'),
)
CELERY_QUEUE_NAMES = frozenset([q.name for q in CELERY_QUEUES])


def attach_database(app, settings=None, _db_master=None):
    # called manually during tests
    if _db_master is None:  # pragma: no cover
        db_master = Database(settings['db_master'])
    else:
        db_master = _db_master
    app.db_master = db_master


def attach_redis_client(app, settings=None, _redis=None):
    if _redis is None:  # pragma: no cover
        app.redis_client = None
        if 'redis_url' in settings:
            app.redis_client = redis_client(settings['redis_url'])
    else:
        app.redis_client = _redis


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
        CELERY_DEFAULT_QUEUE='default',
        CELERY_QUEUES=CELERY_QUEUES,
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
