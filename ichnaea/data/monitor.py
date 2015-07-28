from sqlalchemy import func
from sqlalchemy.orm import load_only

from ichnaea.models import (
    ApiKey,
    OCIDCell,
)
from ichnaea import util


def monitor_api_key_limits(task):
    result = {}
    try:
        today = util.utcnow().strftime('%Y%m%d')
        keys = task.redis_client.keys('apilimit:*:' + today)
        if keys:
            values = task.redis_client.mget(keys)
            keys = [k.decode('utf-8').split(':')[1] for k in keys]
        else:
            values = []

        names = {}
        if keys:
            with task.db_session(commit=False) as session:
                api_iter = ApiKey.iterkeys(
                    session, keys,
                    extra=lambda query: query.options(
                        load_only('valid_key', 'shortname')))

                for api_key in api_iter:
                    names[api_key.valid_key] = api_key.name

        result = {}
        for k, v in zip(keys, values):
            name = names.get(k, k)
            value = int(v)
            result[name] = value
            task.stats_client.gauge('api.limit', value, tags=['key:' + name])
    except Exception:  # pragma: no cover
        # Log but ignore the exception
        task.raven_client.captureException()
    return result


def monitor_ocid_import(task):
    result = -1
    try:
        now = util.utcnow()
        stats_client = task.stats_client
        with task.db_session(commit=False) as session:
            q = session.query(func.max(OCIDCell.created))
            max_created = q.first()[0]
        if max_created:
            # diff between now and the value, in milliseconds
            diff = now - max_created
            result = (diff.days * 86400 + diff.seconds) * 1000

        stats_client.gauge('table', result, tags=['name:ocid_cell_age'])
    except Exception:  # pragma: no cover
        # Log but ignore the exception
        task.raven_client.captureException()
    return result


def monitor_queue_length(task):
    result = {}
    try:
        redis_client = task.app.redis_client
        stats_client = task.stats_client
        for name in task.app.all_queues:
            result[name] = value = redis_client.llen(name)
            stats_client.gauge('queue', value, tags=['name:' + name])
    except Exception:  # pragma: no cover
        # Log but ignore the exception
        task.raven_client.captureException()
    return result
