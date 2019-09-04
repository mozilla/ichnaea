"""
Contains :ref:`celery settings <celery:configuration>`.
"""

from ichnaea.async.config import TASK_QUEUES
from ichnaea.conf import (
    REDIS_URI,
    TESTING,
)

if TESTING:
    # BBB: Celery 4
    # task_always_eager = True
    # task_eager_propagates = True
    CELERY_ALWAYS_EAGER = True
    CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

# BBB: Celery 4
# broker_url = REDIS_URI
# result_backend = REDIS_URI
BROKER_URL = REDIS_URI
CELERY_RESULT_BACKEND = REDIS_URI

# Based on `Celery / Redis caveats
# <celery.rtfd.org/en/latest/getting-started/brokers/redis.html#caveats>`_.

# BBB: Celery 4
# broker_transport_options = {
#     'socket_connect_timeout': 60,
#     'socket_keepalive': True,
#     'socket_timeout': 30,
#     'visibility_timeout': 43200,
# }
BROKER_TRANSPORT_OPTIONS = {
    'fanout_patterns': True,
    'fanout_prefix': True,
    'socket_connect_timeout': 60,
    'socket_keepalive': True,
    'socket_timeout': 30,
    'visibility_timeout': 43200,
}

# Name of the default queue.

# BBB: Celery 4
# task_default_queue = 'celery_default'
CELERY_DEFAULT_QUEUE = 'celery_default'

# Definition of all queues.

# BBB: Celery 4
# task_queues = TASK_QUEUES
CELERY_QUEUES = TASK_QUEUES

# All modules being searched for @task decorators.

# BBB: Celery 4
# imports = [
#     'ichnaea.data.tasks',
# ]
CELERY_IMPORTS = [
    'ichnaea.data.tasks',
]

# Disable task results.
task_ignore_result = True

# Optimization for a mix of fast and slow tasks.

# BBB: Celery 4
# worker_prefetch_multiplier = 8
# worker_disable_rate_limits = True
# task_compression = 'gzip'
CELERYD_PREFETCH_MULTIPLIER = 8
CELERY_DISABLE_RATE_LIMITS = True
CELERY_MESSAGE_COMPRESSION = 'gzip'

# Internal data format, only accept JSON variants.

# BBB: Celery 4
# accept_content = ['json', 'internal_json']
# result_serializer = 'internal_json'
# task_serializer = 'internal_json'
CELERY_ACCEPT_CONTENT = ['json', 'internal_json']
CELERY_RESULT_SERIALIZER = 'internal_json'
CELERY_TASK_SERIALIZER = 'internal_json'

# cleanup
del REDIS_URI
del TASK_QUEUES
del TESTING
