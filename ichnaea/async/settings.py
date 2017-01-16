"""
Contains :ref:`celery settings <celery:configuration>`.
"""

from ichnaea.async.config import TASK_QUEUES
from ichnaea.config import (
    REDIS_URI,
    TESTING,
)

if TESTING:
    broker_url = REDIS_URI
    result_backend = REDIS_URI
    task_always_eager = True
    task_eager_propagates = True

#: Based on `Celery / Redis caveats
#: <celery.rtfd.org/en/latest/getting-started/brokers/redis.html#caveats>`_.
broker_transport_options = {
    'visibility_timeout': 43200,
}

#: Name of the default queue.
task_default_queue = 'celery_default'

#: Definition of all queues.
task_queues = TASK_QUEUES

#: All modules being searched for @task decorators.
imports = [
    'ichnaea.data.tasks',
]

#: Optimization for a mix of fast and slow tasks.
worker_prefetch_multiplier = 8
worker_disable_rate_limits = True  #: Optimization
task_compression = 'gzip'  #: Optimization

#: Internal data format, only accept JSON variants.
accept_content = ['json', 'internal_json']
result_serializer = 'internal_json'  #: Internal data format
task_serializer = 'internal_json'  #: Internal data format

# cleanup
del REDIS_URI
del TASK_QUEUES
del TESTING
