from celery.app import app_or_default
from celery.signals import worker_process_init

from ichnaea.async.config import (
    attach_database,
    attach_redis_client,
    configure_s3_backup,
    configure_ocid_import,
)
from ichnaea.config import read_config
from ichnaea.heka_logging import configure_heka
from ichnaea.stats import configure_stats


@worker_process_init.connect
def init_worker_process(signal, sender, **kw):  # pragma: no cover
    # called automatically when `celery worker` is started
    # get the app in the current worker process
    app = app_or_default()
    conf = read_config()
    settings = conf.get_map('ichnaea')
    attach_database(app, settings=settings)
    attach_redis_client(app, settings=settings)
    configure_s3_backup(app, settings=settings)
    configure_ocid_import(app, settings=settings)
    configure_heka(conf.filename)
    configure_stats(settings.get('statsd_host'))
