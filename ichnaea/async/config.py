"""
Contains celery specific one time configuration code.
"""

import os

from kombu import Queue
from kombu.serialization import register
import simplejson

from ichnaea.cache import configure_redis
from ichnaea.config import read_config
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
from ichnaea.queue import DataQueue
from ichnaea.data.export import ExportQueue

CELERY_QUEUES = (
    Queue('celery_blue', routing_key='celery_blue'),
    Queue('celery_cell', routing_key='celery_cell'),
    Queue('celery_content', routing_key='celery_content'),
    Queue('celery_default', routing_key='celery_default'),
    Queue('celery_export', routing_key='celery_export'),
    Queue('celery_incoming', routing_key='celery_incoming'),
    Queue('celery_monitor', routing_key='celery_monitor'),
    Queue('celery_ocid', routing_key='celery_ocid'),
    Queue('celery_reports', routing_key='celery_reports'),
    Queue('celery_upload', routing_key='celery_upload'),  # BBB
    Queue('celery_wifi', routing_key='celery_wifi'),
)  #: List of :class:`kombu.Queue` instances.

register('internal_json',
         simplejson.dumps,
         simplejson.loads,
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

    # This happens at module import time and depends on a properly
    # set ICHNAEA_CFG.
    app_config = read_config()
    if not app_config.has_section('celery'):  # pragma: no cover
        # Happens while building docs locally.
        return

    # Make config file settings available.
    celery_app.app_config = app_config
    celery_app.settings = app_config.asdict()

    # testing settings
    always_eager = bool(os.environ.get('CELERY_ALWAYS_EAGER', False))
    redis_uri = os.environ.get('REDIS_URI')

    if always_eager and redis_uri:
        broker_url = redis_uri
        result_url = redis_uri
    else:  # pragma: no cover
        celery_section = app_config.get_map('celery')
        broker_url = celery_section['broker_url']
        result_url = celery_section['result_url']

    celery_app.config_from_object('ichnaea.async.settings')
    celery_app.conf.update(
        BROKER_URL=broker_url,
        CELERY_RESULT_BACKEND=result_url,
        CELERY_QUEUES=CELERY_QUEUES,
    )


def configure_data(redis_client):
    """
    Configure fixed set of data queues.
    """
    data_queues = {
        # update_incoming needs to be the exact same as in webapp.config
        'update_incoming': DataQueue('update_incoming', redis_client,
                                     batch=100, compress=True),
        'update_score': DataQueue('update_score', redis_client,
                                  batch=100),
    }
    for key in ('update_cellarea', 'update_cellarea_ocid'):
        data_queues[key] = DataQueue(key, redis_client, batch=100, json=False)
    for shard_id in BlueShard.shards().keys():
        key = 'update_blue_' + shard_id
        data_queues[key] = DataQueue(key, redis_client, batch=500)
    for shard_id in DataMap.shards().keys():
        key = 'update_datamap_' + shard_id
        data_queues[key] = DataQueue(key, redis_client, batch=500, json=False)
    for shard_id in CellShard.shards().keys():
        key = 'update_cell_' + shard_id
        data_queues[key] = DataQueue(key, redis_client, batch=500)
    for shard_id in WifiShard.shards().keys():
        key = 'update_wifi_' + shard_id
        data_queues[key] = DataQueue(key, redis_client, batch=500)
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
            key = 'queue_export_' + section_name.split(':')[1]
            export_queues[key] = ExportQueue.configure_queue(
                key, redis_client, section)
    return export_queues


def init_beat(beat, celery_app):
    """
    Configure the passed in celery beat app, usually stored in
    :data:`ichnaea.async.app.celery_app`.
    """
    # Ensure we import all tasks in the context of the beat process,
    # as these configure their own beat schedule.
    celery_app.loader.import_default_modules()


def init_worker(celery_app,
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

    # configure outside connections
    celery_app.db_rw = configure_db(
        celery_app.app_config.get('database', 'rw_url'), _db=_db_rw)

    celery_app.raven_client = raven_client = configure_raven(
        celery_app.app_config.get('sentry', 'dsn'),
        transport='threaded', _client=_raven_client)

    celery_app.redis_client = redis_client = configure_redis(
        celery_app.app_config.get('cache', 'cache_url'), _client=_redis_client)

    celery_app.stats_client = configure_stats(
        celery_app.app_config, _client=_stats_client)

    celery_app.geoip_db = configure_geoip(
        celery_app.app_config.get('geoip', 'db_path'),
        raven_client=raven_client, _client=_geoip_db)

    # configure data / export queues
    celery_app.all_queues = all_queues = set([q.name for q in CELERY_QUEUES])

    celery_app.data_queues = data_queues = configure_data(redis_client)
    for queue in data_queues.values():
        if queue.monitor_name:
            all_queues.add(queue.monitor_name)

    celery_app.export_queues = configure_export(
        redis_client, celery_app.app_config)


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
    del celery_app.app_config
