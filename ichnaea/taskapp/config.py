"""
Contains celery specific one-time configuration code.
"""

from kombu import Queue

from ichnaea.cache import configure_redis
from ichnaea.db import configure_db
from ichnaea.geoip import configure_geoip
from ichnaea.log import configure_raven, configure_stats
from ichnaea.models import BlueShard, CellShard, DataMap, WifiShard
from ichnaea.queue import DataQueue

TASK_QUEUES = (
    Queue("celery_blue", routing_key="celery_blue"),
    Queue("celery_cell", routing_key="celery_cell"),
    Queue("celery_content", routing_key="celery_content"),
    Queue("celery_default", routing_key="celery_default"),
    Queue("celery_export", routing_key="celery_export"),
    Queue("celery_monitor", routing_key="celery_monitor"),
    Queue("celery_reports", routing_key="celery_reports"),
    Queue("celery_wifi", routing_key="celery_wifi"),
)


def configure_celery(celery_app):
    """
    Configure the celery app stored in :data:`ichnaea.taskapp.app.celery_app`.
    This is executed both inside the supervisor worker process and once in
    each child / thread worker process.

    This parses the application ini and reads in the
    :mod:`ichnaea.taskapp.settings`.
    """
    celery_app.config_from_object("ichnaea.taskapp.settings")


def configure_data(redis_client):
    """
    Configure fixed set of data queues.
    """
    data_queues = {
        # *_incoming need to be the exact same as in webapp.config
        "update_incoming": DataQueue(
            "update_incoming", redis_client, "report", batch=5000, compress=True
        )
    }
    for key in ("update_cellarea",):
        data_queues[key] = DataQueue(
            key, redis_client, "cellarea", batch=100, json=False
        )
    for shard_id in BlueShard.shards().keys():
        key = "update_blue_" + shard_id
        data_queues[key] = DataQueue(key, redis_client, "bluetooth", batch=500)
    for shard_id in DataMap.shards().keys():
        key = "update_datamap_" + shard_id
        data_queues[key] = DataQueue(
            key, redis_client, "datamap", batch=500, json=False
        )
    for shard_id in CellShard.shards().keys():
        key = "update_cell_" + shard_id
        data_queues[key] = DataQueue(key, redis_client, "cell", batch=500)
    for shard_id in WifiShard.shards().keys():
        key = "update_wifi_" + shard_id
        data_queues[key] = DataQueue(key, redis_client, "wifi", batch=500)
    return data_queues


def init_beat(beat, celery_app):
    """
    Configure the passed in celery beat app, usually stored in
    :data:`ichnaea.taskapp.app.celery_app`.
    """
    # Ensure we import all tasks in the context of the beat process,
    # as these configure their own beat schedule.
    celery_app.loader.import_default_modules()


def init_worker(
    celery_app, _db=None, _geoip_db=None, _raven_client=None, _redis_client=None
):
    """
    Configure the passed in celery app, usually stored in
    :data:`ichnaea.taskapp.app.celery_app`.

    Does connection, settings and queue setup. Attaches some
    additional functionality to the :class:`celery.Celery` instance.

    This is executed inside each forked worker process.

    The parameters starting with an underscore are test-only hooks
    to provide pre-configured connection objects.
    """

    # configure outside connections
    celery_app.db = configure_db("rw", _db=_db)

    celery_app.raven_client = raven_client = configure_raven(
        transport="threaded", tags={"app": "taskapp"}, _client=_raven_client
    )

    celery_app.redis_client = redis_client = configure_redis(_client=_redis_client)

    configure_stats()

    celery_app.geoip_db = configure_geoip(raven_client=raven_client, _client=_geoip_db)

    # configure data queues and build set of all queues
    all_queues = {q.name: {"queue_type": "task"} for q in TASK_QUEUES}
    celery_app.data_queues = data_queues = configure_data(redis_client)
    all_queues.update(
        {queue.key: queue.tags for queue in data_queues.values() if queue.key}
    )
    celery_app.all_queues = all_queues


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
    celery_app.geoip_db.close()
    del celery_app.geoip_db

    del celery_app.all_queues
    del celery_app.data_queues
