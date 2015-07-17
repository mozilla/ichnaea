"""
Contains :ref:`celery settings <celery:configuration>`.
"""

import os

always_eager = bool(os.environ.get('CELERY_ALWAYS_EAGER', False))

#: Set based on the environment variable of the same name.
CELERY_ALWAYS_EAGER = always_eager
#: Set to the same value as CELERY_ALWAYS_EAGER.
CELERY_EAGER_PROPAGATES_EXCEPTIONS = always_eager

#: Based on `Celery / Redis caveats
#: <celery.rtfd.org/en/latest/getting-started/brokers/redis.html#caveats>`_.
BROKER_TRANSPORT_OPTIONS = {
    'fanout_patterns': True,
    'fanout_prefix': True,
    'visibility_timeout': 3600,
}

#: Name of the default queue.
CELERY_DEFAULT_QUEUE = 'celery_default'

#: All modules being searched for @task decorators.
CELERY_IMPORTS = [
    'ichnaea.data.tasks',
    'ichnaea.export.tasks',
    'ichnaea.monitor.tasks',
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
del always_eager
del os
