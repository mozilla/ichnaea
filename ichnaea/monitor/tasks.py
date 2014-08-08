from ichnaea.async.config import CELERY_QUEUE_NAMES
from ichnaea.async.task import DatabaseTask
from ichnaea.worker import celery


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
