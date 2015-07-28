from ichnaea.async.app import celery_app
from ichnaea.async.task import BaseTask


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor')
def monitor_api_key_limits(self):  # pragma: no cover
    # BBB
    pass


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor')
def monitor_ocid_import(self):  # pragma: no cover
    # BBB
    pass


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor')
def monitor_queue_length(self):  # pragma: no cover
    # BBB
    pass
