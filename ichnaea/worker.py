from celery import Celery

from ichnaea.async.config import configure_celery

# Ensure worker_process_init decorator is picked up
from ichnaea.async.worker import init_worker_process  # NOQA

celery = Celery('ichnaea.worker')

configure_celery(celery)
