"""
Contains celery specific one time configuration code.
"""

from kombu import Queue
from kombu.serialization import register
import simplejson

from ichnaea.cache import configure_redis
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

TASK_QUEUES = (
    Queue('celery_blue', routing_key='celery_blue'),
    Queue('celery_cell', routing_key='celery_cell'),
    Queue('celery_content', routing_key='celery_content'),
    Queue('celery_default', routing_key='celery_default'),
    Queue('celery_export', routing_key='celery_export'),
    Queue('celery_incoming', routing_key='celery_incoming'),
    Queue('celery_monitor', routing_key='celery_monitor'),
    Queue('celery_reports', routing_key='celery_reports'),
    Queue('celery_wifi', routing_key='celery_wifi'),
)

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
    celery_app.config_from_object('ichnaea.async.settings')


def configure_data(redis_client):
    """
    Configure fixed set of data queues.
    """
    data_queues = {
        # *_incoming need to be the exact same as in webapp.config
        'update_incoming': DataQueue('update_incoming', redis_client,
                                     batch=100, compress=True),
        'transfer_incoming': DataQueue('transfer_incoming', redis_client,
                                       batch=100, compress=True),
    }
    for key in ('update_cellarea', ):
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


def init_beat(beat, celery_app):
    """
    Configure the passed in celery beat app, usually stored in
    :data:`ichnaea.async.app.celery_app`.
    """
    # Ensure we import all tasks in the context of the beat process,
    # as these configure their own beat schedule.
    celery_app.loader.import_default_modules()


def init_worker(celery_app,
                _db=None, _geoip_db=None,
                _raven_client=None, _redis_client=None, _stats_client=None):
    """
    Configure the passed in celery app, usually stored in
    :data:`ichnaea.async.app.celery_app`.

    Does connection, settings and queue setup. Attaches some
    additional functionality to the :class:`celery.Celery` instance.

    This is executed inside each forked worker process.

    The parameters starting with an underscore are test-only hooks
    to provide pre-configured connection objects.
    """

    # configure outside connections
    celery_app.db = configure_db('rw', _db=_db)

    celery_app.raven_client = raven_client = configure_raven(
        transport='threaded', _client=_raven_client)

    celery_app.redis_client = redis_client = configure_redis(
        _client=_redis_client)

    celery_app.stats_client = configure_stats(_client=_stats_client)

    celery_app.geoip_db = configure_geoip(
        raven_client=raven_client, _client=_geoip_db)

    # configure data queues
    celery_app.all_queues = all_queues = set([q.name for q in TASK_QUEUES])

    celery_app.data_queues = data_queues = configure_data(redis_client)
    all_queues = all_queues.union(
        set([queue.key for queue in data_queues.values() if queue.key]))


def shutdown_worker(celery_app):
    """
    Close outbound connections and remove custom celery_app state.

    This is executed inside each forked worker process.
    """
    celery_app.db.close()
    del celery_app.db
    del celery_app.raven_client
    celery_app.redis_client.close()
    del celery_app.redis_client
    celery_app.stats_client.close()
    del celery_app.stats_client
    celery_app.geoip_db.close()
    del celery_app.geoip_db

    del celery_app.all_queues
    del celery_app.data_queues
