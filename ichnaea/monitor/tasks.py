from ichnaea.async.config import CELERY_QUEUE_NAMES
from ichnaea.models import ApiKey
from ichnaea.async.task import DatabaseTask
from ichnaea import util
from ichnaea.worker import celery


@celery.task(base=DatabaseTask, bind=True, queue='monitor')
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


@celery.task(base=DatabaseTask, bind=True, queue='monitor')
def monitor_queue_length(self):
    result = {}
    try:
        redis_client = self.app.redis_client
        stats_client = self.stats_client
        for name in CELERY_QUEUE_NAMES:
            result[name] = value = redis_client.llen(name)
            stats_client.gauge('queue.' + name, value)
    except Exception:  # pragma: no cover
        # Log but ignore the exception
        self.heka_client.raven('error')
    return result
