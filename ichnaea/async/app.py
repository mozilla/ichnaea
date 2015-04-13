from celery import Celery
from celery.app import app_or_default
from celery.signals import worker_process_init

from ichnaea.async.config import (
    configure_celery,
    init_worker,
)
from ichnaea.config import read_config


@worker_process_init.connect
def init_worker_process(signal, sender, **kw):  # pragma: no cover
    # called automatically when `celery worker` is started
    # get the app in the current worker process
    celery_app = app_or_default()
    conf = read_config()
    init_worker(celery_app, conf)

# Actual Celery app endpoint, used on the command line via:
# bin/celery -A ichnaea.async.app:celery_app <worker, beat>
celery_app = Celery('ichnaea.async.app')

configure_celery(celery_app)
