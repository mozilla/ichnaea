import os
# from datetime import timedelta

from celery import Celery
from celery.signals import worker_init
# from celery.schedules import crontab

from ichnaea import config
from ichnaea.db import Database


CELERY_IMPORTS = ['ichnaea.tasks']
CELERYBEAT_SCHEDULE = {
    # 'add-every-day': {
    #     'task': 'ichnaea.tasks.add_measure',
    #     'schedule': crontab(hour=0, minute=17),
    #     'args': (16, 16),
    # },
    # 'add-often': {
    #     'task': 'ichnaea.tasks.add_measure',
    #     'schedule': timedelta(seconds=5),
    #     'args': (6, 9),
    # },
}

celery = Celery('ichnaea.worker')


def attach_database(app, _db_master=None):
    # called manually during tests
    settings = config().get_map('ichnaea')
    if _db_master is None:  # pragma: no cover
        db_master = Database(
            settings['db_master'],
            socket=settings.get('db_master_socket'),
        )
    else:
        db_master = _db_master
    app.db_master = db_master


@worker_init.connect
def init_worker(signal, sender):  # pragma: no cover
    # called automatically when `celery worker` is started
    attach_database(sender.app)


def configure(celery=celery):
    conf = config()
    if conf.has_section('celery'):
        section = conf.get_map('celery')
    else:  # pragma: no cover
        section = {}

    database_options = {
        "pool_recycle": 3600,
        "pool_size": 10,
        "pool_timeout": 10,
        "isolation_level": "READ COMMITTED",
    }

    # testing overrides
    sqluri = os.environ.get('SQLURI', '')
    sqlsocket = os.environ.get('SQLSOCKET', '')

    if sqluri:
        broker_url = sqluri
        result_url = sqluri
    else:  # pragma: no cover
        broker_url = section['broker_url']
        result_url = section['result_url']

    broker_url = 'sqla+' + broker_url

    if sqlsocket:
        broker_socket = sqlsocket
        result_socket = sqluri
    else:  # pragma: no cover
        broker_socket = section['broker_socket']
        result_socket = section['result_socket']

    broker_connect_args = {"charset": "utf8"}
    if broker_socket:
        broker_connect_args['unix_socket'] = broker_socket
    broker_options = database_options.copy()
    broker_options['connect_args'] = broker_connect_args

    result_connect_args = {"charset": "utf8"}
    if result_socket:
        result_connect_args['unix_socket'] = result_socket
    result_options = database_options.copy()
    result_options['connect_args'] = result_connect_args

    # testing setting
    always_eager = bool(os.environ.get('CELERY_ALWAYS_EAGER', False))

    celery.conf.update(
        # testing
        CELERY_ALWAYS_EAGER=always_eager,
        CELERY_EAGER_PROPAGATES_EXCEPTIONS=always_eager,
        # broker
        BROKER_URL=broker_url,
        BROKER_TRANSPORT_OPTIONS=broker_options,
        # results
        CELERY_RESULT_BACKEND='database',
        CELERY_RESULT_DBURI=result_url,
        CELERY_RESULT_ENGINE_OPTIONS=result_options,
        # tasks
        CELERY_IMPORTS=CELERY_IMPORTS,
        # default to idempotent tasks
        CELERY_ACKS_LATE=True,
        # forward compatibility
        CELERYD_FORCE_EXECV=True,
        # optimization
        CELERY_DISABLE_RATE_LIMITS=True,
        # security
        CELERY_ACCEPT_CONTENT=['json'],
        CELERY_RESULT_SERIALIZER='json',
        CELERY_TASK_SERIALIZER='json',
        # schedule
        CELERYBEAT_LOG_LEVEL="INFO",
        CELERYBEAT_SCHEDULE=CELERYBEAT_SCHEDULE,
    )

configure(celery)
