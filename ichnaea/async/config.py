"""
Contains celery specific one time configuration code.
"""

import os

from kombu import Queue
from kombu.serialization import register

from ichnaea.async.schedule import celerybeat_schedule
from ichnaea.cache import configure_redis
from ichnaea.config import read_config
from ichnaea import internaljson
from ichnaea.db import configure_db
from ichnaea.geoip import configure_geoip
from ichnaea.log import (
    configure_raven,
    configure_stats,
)
from ichnaea.models import (
    BlueShard,
    CellShard,
    DataMap,
    WifiShard,
)
from ichnaea.queue import (
    DataQueue,
    ExportQueue,
)

CELERY_QUEUES = (
    Queue('celery_blue', routing_key='celery_blue'),
    Queue('celery_cell', routing_key='celery_cell'),
    Queue('celery_default', routing_key='celery_default'),
    Queue('celery_export', routing_key='celery_export'),
    Queue('celery_incoming', routing_key='celery_incoming'),
    Queue('celery_monitor', routing_key='celery_monitor'),
    Queue('celery_ocid', routing_key='celery_ocid'),
    Queue('celery_reports', routing_key='celery_reports'),
    Queue('celery_upload', routing_key='celery_upload'),
    Queue('celery_wifi', routing_key='celery_wifi'),
)  #: List of :class:`kombu.Queue` instances.

register('internal_json',
         internaljson.internal_dumps,
         internaljson.internal_loads,
         content_type='application/x-internaljson',
         content_encoding='utf-8')


def configure_celery(celery_app):
    """
    Configure the celery app stored in :data:`ichnaea.async.app.celery_app`.
    This is executed both inside the master worker process and once in
    each forked worker process.

    This parses the application ini and reads in the
    :mod:`ichnaea.async.settings`.
    """

    conf = read_config()
    if conf.has_section('celery'):
        section = conf.get_map('celery')
    else:  # pragma: no cover
        # happens while building docs locally
        return

    # testing settings
    always_eager = bool(os.environ.get('CELERY_ALWAYS_EAGER', False))
    redis_uri = os.environ.get('REDIS_URI')

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
        CELERYBEAT_SCHEDULE=celerybeat_schedule(conf),
    )


def configure_data(redis_client):
    """
    Configure fixed set of data queues.
    """
    data_queues = {
        'update_cellarea': DataQueue('update_cellarea', redis_client,
                                     queue_key='update_cellarea'),
        'update_cellarea_ocid': DataQueue('update_cellarea_ocid', redis_client,
                                          queue_key='update_cellarea_ocid'),
        'update_incoming': DataQueue('update_incoming', redis_client,
                                     queue_key='update_incoming',
                                     compress=True),
        'update_score': DataQueue('update_score', redis_client,
                                  queue_key='update_score'),
    }
    for shard_id in BlueShard.shards().keys():
        name = 'update_blue_' + shard_id
        data_queues[name] = DataQueue(
            name, redis_client, queue_key=name)
    for shard_id in DataMap.shards().keys():
        name = 'update_datamap_' + shard_id
        data_queues[name] = DataQueue(name, redis_client, queue_key=name)
    for shard_id in CellShard.shards().keys():
        name = 'update_cell_' + shard_id
        data_queues[name] = DataQueue(
            name, redis_client, queue_key=name)
    for shard_id in WifiShard.shards().keys():
        name = 'update_wifi_' + shard_id
        data_queues[name] = DataQueue(
            name, redis_client, queue_key=name)
    return data_queues


def configure_export(redis_client, app_config):
    """
    Configure export queues, based on the `[export:*]` sections from
    the application ini file.
    """
    export_queues = {}
    for section_name in app_config.sections():
        if section_name.startswith('export:'):
            section = app_config.get_map(section_name)
            name = section_name.split(':')[1]
            export_queues[name] = ExportQueue(name, redis_client, section)
    return export_queues


def init_worker(celery_app, app_config,
                _db_rw=None, _db_ro=None, _geoip_db=None,
                _raven_client=None, _redis_client=None, _stats_client=None):
    """
    Configure the passed in celery app, usually stored in
    :data:`ichnaea.async.app.celery_app`.

    Does connection, settings and queue setup. Attaches some
    additional functionality to the :class:`celery.Celery` instance.

    This is executed inside each forked worker process.

    The parameters starting with an underscore are test-only hooks
    to provide pre-configured connection objects.

    :param _db_ro: Ignored, read-only database connection isn't used.
    """

    # make config file settings available
    celery_app.settings = app_config.asdict()

    # configure outside connections
    celery_app.db_rw = configure_db(
        app_config.get('database', 'rw_url'), _db=_db_rw)

    celery_app.raven_client = raven_client = configure_raven(
        app_config.get('sentry', 'dsn'),
        transport='threaded', _client=_raven_client)

    celery_app.redis_client = redis_client = configure_redis(
        app_config.get('cache', 'cache_url'), _client=_redis_client)

    celery_app.stats_client = configure_stats(
        app_config, _client=_stats_client)

    celery_app.geoip_db = configure_geoip(
        app_config.get('geoip', 'db_path'), raven_client=raven_client,
        _client=_geoip_db)

    # configure data / export queues
    celery_app.all_queues = all_queues = set([q.name for q in CELERY_QUEUES])

    celery_app.data_queues = data_queues = configure_data(redis_client)
    for queue in data_queues.values():
        if queue.monitor_name:
            all_queues.add(queue.monitor_name)

    celery_app.export_queues = configure_export(redis_client, app_config)
    for queue in celery_app.export_queues.values():
        if queue.monitor_name:
            all_queues.add(queue.monitor_name)


def shutdown_worker(celery_app):
    """
    Close outbound connections and remove custom celery_app state.

    This is executed inside each forked worker process.
    """
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
