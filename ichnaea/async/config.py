import os

from kombu import Queue
from kombu.serialization import register

from ichnaea.async.schedule import CELERYBEAT_SCHEDULE
from ichnaea.cache import configure_redis
from ichnaea.config import read_config
from ichnaea import customjson
from ichnaea.db import configure_db
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
EXPORT_QUEUE_PREFIX = 'queue_export_'

register('internal_json', customjson.kombu_dumps, customjson.kombu_loads,
         content_type='application/x-internaljson',
         content_encoding='utf-8')


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


def init_worker(celery_app, app_config,
                _db_rw=None, _db_ro=None, _geoip_db=None,
                _raven_client=None, _redis_client=None, _stats_client=None):
    # currently neither a db_ro nor geoip_db are set up

    # make config file settings available
    celery_app.settings = app_config.asdict()

    # configure data / export queues
    celery_app.all_queues = all_queues = set([q.name for q in CELERY_QUEUES])

    celery_app.data_queues = data_queues = {
        'cell_area_update': 'update_cell_lac',
    }
    for value in data_queues.values():
        all_queues.add(value)

    celery_app.export_queues = export_queues = {}
    for section_name in app_config.sections():
        if section_name.startswith('export:'):
            section = app_config.get_map(section_name)
            name = section_name.split(':')[1]
            queue_name = EXPORT_QUEUE_PREFIX + name
            export_queues[name] = {
                'redis_key': queue_name,
            }
            all_queues.add(queue_name)
            for key, value in section.items():
                if key == 'batch':
                    export_queues[name][key] = int(value)
                else:
                    export_queues[name][key] = value

    # configure outside connections
    celery_app.db_rw = configure_db(
        app_config.get('ichnaea', 'db_master'), _db=_db_rw)

    celery_app.raven_client = configure_raven(
        app_config.get('ichnaea', 'sentry_dsn'),
        transport='threaded', _client=_raven_client)

    celery_app.redis_client = configure_redis(
        app_config.get('ichnaea', 'redis_url'), _client=_redis_client)

    celery_app.stats_client = configure_stats(
        app_config.get('ichnaea', 'statsd_host'), _client=_stats_client)


def shutdown_worker(celery_app):
    # close outbound connections / remove custom instance state
    celery_app.db_rw.engine.pool.dispose()
    del celery_app.db_rw

    del celery_app.raven_client

    celery_app.redis_client.connection_pool.disconnect()
    del celery_app.redis_client

    del celery_app.stats_client

    del celery_app.all_queues
    del celery_app.data_queues
    del celery_app.export_queues
    del celery_app.settings
