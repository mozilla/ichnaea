from sqlalchemy import func
from sqlalchemy.orm import load_only

from ichnaea.async.app import celery_app
from ichnaea.async.task import BaseTask
from ichnaea.models import (
    ApiKey,
    OCIDCell,
)
from ichnaea import util


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor')
def monitor_api_key_limits(self):
    result = {}
    try:
        today = util.utcnow().strftime('%Y%m%d')
        keys = self.redis_client.keys('apilimit:*:' + today)
        if keys:
            values = self.redis_client.mget(keys)
            keys = [k.split(':')[1] for k in keys]
        else:
            values = []

        names = {}
        if keys:
            with self.db_session(commit=False) as session:
                query = (ApiKey.querykeys(session, keys)
                               .options(load_only('valid_key', 'shortname')))
                for api_key in query.all():
                    names[api_key.valid_key] = api_key.name

        result = {}
        for k, v in zip(keys, values):
            name = names.get(k, k)
            value = int(v)
            result[name] = value
            self.stats_client.gauge('apilimit.' + name, value)
    except Exception:  # pragma: no cover
        # Log but ignore the exception
        self.raven_client.captureException()
    return result


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor')
def monitor_ocid_import(self):
    result = -1
    try:
        now = util.utcnow()
        stats_client = self.stats_client
        with self.db_session(commit=False) as session:
            q = session.query(func.max(OCIDCell.created))
            max_created = q.first()[0]
        if max_created:
            # diff between now and the value, in milliseconds
            diff = now - max_created
            result = (diff.days * 86400 + diff.seconds) * 1000

        stats_client.gauge('table.ocid_cell_age', result)
    except Exception:  # pragma: no cover
        # Log but ignore the exception
        self.raven_client.captureException()
    return result


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor')
def monitor_queue_length(self):
    result = {}
    try:
        redis_client = self.app.redis_client
        stats_client = self.stats_client
        for name in self.app.all_queues:
            result[name] = value = redis_client.llen(name)
            stats_client.gauge('queue.' + name, value)
    except Exception:  # pragma: no cover
        # Log but ignore the exception
        self.raven_client.captureException()
    return result
