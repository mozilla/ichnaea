from celery import Celery
from celery.app import app_or_default
from celery.signals import worker_process_init

from ichnaea.async.config import (
    attach_database,
    attach_raven_client,
    attach_redis_client,
    attach_stats_client,
    configure_celery,
    configure_s3_backup,
    configure_ocid_import,
)
from ichnaea.config import read_config


@worker_process_init.connect
def init_worker_process(signal, sender, **kw):  # pragma: no cover
    # called automatically when `celery worker` is started
    # get the app in the current worker process
    app = app_or_default()
    conf = read_config()
    settings = conf.get_map('ichnaea')
    attach_database(app, settings=settings)
    attach_raven_client(app, settings=settings)
    attach_redis_client(app, settings=settings)
    attach_stats_client(app, settings=settings)
    configure_s3_backup(app, settings=settings)
    configure_ocid_import(app, settings=settings)

# Actual Celery app endpoint, used on the command line via:
# bin/celery -A ichnaea.async.app:celery_app <worker, beat>
celery_app = Celery('ichnaea.async.app')

configure_celery(celery_app)
