"""
Contains :ref:`celery settings <celery:configuration>`.
"""

from ichnaea.async.config import CELERY_QUEUES
from ichnaea.config import (
    REDIS_URI,
    TESTING,
)

if TESTING:
    CELERY_ALWAYS_EAGER = True
    CELERY_EAGER_PROPAGATES_EXCEPTIONS = True
    BROKER_URL = REDIS_URI
    CELERY_RESULT_BACKEND = REDIS_URI

#: Based on `Celery / Redis caveats
#: <celery.rtfd.org/en/latest/getting-started/brokers/redis.html#caveats>`_.
BROKER_TRANSPORT_OPTIONS = {
    'fanout_patterns': True,
    'fanout_prefix': True,
    'visibility_timeout': 3600,
}

#: Name of the default queue.
CELERY_DEFAULT_QUEUE = 'celery_default'

#: Definition of all queues.
CELERY_QUEUES = CELERY_QUEUES

#: All modules being searched for @task decorators.
CELERY_IMPORTS = [
    'ichnaea.data.tasks',
]

#: Optimization for a mix of fast and slow tasks.
CELERYD_PREFETCH_MULTIPLIER = 8
CELERY_DISABLE_RATE_LIMITS = True  #: Optimization
CELERY_MESSAGE_COMPRESSION = 'gzip'  #: Optimization

#: Internal data format, only accept JSON variants.
CELERY_ACCEPT_CONTENT = ['json', 'internal_json']
CELERY_RESULT_SERIALIZER = 'internal_json'  #: Internal data format
CELERY_TASK_SERIALIZER = 'internal_json'  #: Internal data format

CELERYBEAT_LOG_LEVEL = 'WARNING'  #: Silence celery beat.

# cleanup
del REDIS_URI
del TESTING
