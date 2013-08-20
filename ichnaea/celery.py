from __future__ import absolute_import
from datetime import timedelta

from celery import Celery
from celery.schedules import crontab


celery = Celery('ichnaea.celery')

celery.conf.update(
    # testing
    # CELERY_ALWAYS_EAGER=True,
    # CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    # broker
    BROKER_URL='sqla+mysql+pymysql://root:mysql@localhost/location',
    BROKER_TRANSPORT_OPTIONS={
        "pool_recycle": 3600,
        "pool_size": 10,
        "pool_timeout": 10,
        "isolation_level": "READ COMMITTED",
        "connect_args": {
            "charset": "utf8",
            "unix_socket": "/opt/local/var/run/mysql56/mysqld.sock",
        },
    },
    # results
    CELERY_RESULT_BACKEND='database',
    CELERY_RESULT_DBURI='mysql+pymysql://root:mysql@localhost/location',
    CELERY_RESULT_ENGINE_OPTIONS={
        "pool_recycle": 3600,
        "pool_size": 10,
        "pool_timeout": 10,
        "isolation_level": "READ COMMITTED",
        "connect_args": {
            "charset": "utf8",
            "unix_socket": "/opt/local/var/run/mysql56/mysqld.sock",
        },
    },
    # tasks
    CELERY_IMPORTS=['ichnaea.tasks'],
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
    CELERYBEAT_SCHEDULE={
        'add-every-day': {
            'task': 'ichnaea.tasks.add',
            'schedule': crontab(hour=0, minute=17),
            'args': (16, 16),
        },
        'add-often': {
            'task': 'ichnaea.tasks.add',
            'schedule': timedelta(seconds=5),
            'args': (6, 9),
        },
    },
)

if __name__ == '__main__':
    celery.start()
