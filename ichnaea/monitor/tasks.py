from sqlalchemy import func

from ichnaea.async.config import CELERY_QUEUE_NAMES
from ichnaea.async.task import DatabaseTask
from ichnaea.data.area import UPDATE_KEY
from ichnaea.models import (
    ApiKey,
    CellObservation,
    OCIDCell,
    WifiObservation,
)
from ichnaea import util
from ichnaea.worker import celery

# combine celery queues and manual update queues
MONITOR_QUEUE_NAMES = set(CELERY_QUEUE_NAMES).union(set(UPDATE_KEY.values()))


@celery.task(base=DatabaseTask, bind=True, queue='celery_monitor')
def monitor_api_key_limits(self):
    result = {}
    try:
        redis_client = self.app.redis_client
        stats_client = self.stats_client
        now = util.utcnow()
        today = now.strftime("%Y%m%d")

        keys = redis_client.keys('apilimit:*:' + today)
        if keys:
            values = redis_client.mget(keys)
            keys = [k.split(':')[1] for k in keys]
        else:
            values = []

        names = {}
        if keys:
            with self.db_session() as session:
                q = session.query(ApiKey.valid_key, ApiKey.shortname).filter(
                    ApiKey.valid_key.in_(keys))
                names = dict(q.all())

        result = {}
        for k, v in zip(keys, values):
            name = names.get(k)
            if not name:
                name = k
            value = int(v)
            result[name] = value
            stats_client.gauge('apilimit.' + name, value)
    except Exception:  # pragma: no cover
        # Log but ignore the exception
        self.heka_client.raven('error')
    return result


@celery.task(base=DatabaseTask, bind=True, queue='celery_monitor')
def monitor_measures(self):
    checks = [('cell_measure', CellObservation),
              ('wifi_measure', WifiObservation)]
    result = dict([(name, -1) for name, model in checks])
    try:
        stats_client = self.stats_client
        with self.db_session() as session:
            for name, model in checks:
                # record current number of db rows in *_measure table
                q = session.query(func.max(model.id) - func.min(model.id) + 1)
                num_rows = q.first()[0]
                if num_rows is None:
                    num_rows = -1
                result[name] = num_rows
                stats_client.gauge('table.' + name, num_rows)
    except Exception:  # pragma: no cover
        # Log but ignore the exception
        self.heka_client.raven('error')
    return result


@celery.task(base=DatabaseTask, bind=True, queue='celery_monitor')
def monitor_ocid_import(self):
    result = -1
    try:
        now = util.utcnow()
        stats_client = self.stats_client
        with self.db_session() as session:
            q = session.query(func.max(OCIDCell.created))
            max_created = q.first()[0]
        if max_created:
            # diff between now and the value, in milliseconds
            diff = now - max_created
            result = (diff.days * 86400 + diff.seconds) * 1000

        stats_client.gauge('table.ocid_cell_age', result)
    except Exception:  # pragma: no cover
        # Log but ignore the exception
        self.heka_client.raven('error')
    return result


@celery.task(base=DatabaseTask, bind=True, queue='celery_monitor')
def monitor_queue_length(self):
    result = {}
    try:
        redis_client = self.app.redis_client
        stats_client = self.stats_client
        for name in MONITOR_QUEUE_NAMES:
            result[name] = value = redis_client.llen(name)
            stats_client.gauge('queue.' + name, value)
    except Exception:  # pragma: no cover
        # Log but ignore the exception
        self.heka_client.raven('error')
    return result
