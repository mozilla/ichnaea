import os

always_eager = bool(os.environ.get('CELERY_ALWAYS_EAGER', False))

# testing
CELERY_ALWAYS_EAGER = always_eager
CELERY_EAGER_PROPAGATES_EXCEPTIONS = always_eager
# broker
BROKER_TRANSPORT_OPTIONS = {
    # Based on celery / redis caveats
    # celery.rtfd.org/en/latest/getting-started/brokers/redis.html#caveats
    'fanout_patterns': True,
    'fanout_prefix': True,
    'visibility_timeout': 3600,
}
# queues
CELERY_DEFAULT_QUEUE = 'celery_default'
# tasks
CELERY_IMPORTS = [
    'ichnaea.backup.tasks',
    'ichnaea.data.tasks',
    'ichnaea.export.tasks',
    'ichnaea.monitor.tasks',
]
# optimization
CELERYD_PREFETCH_MULTIPLIER = 8
CELERY_DISABLE_RATE_LIMITS = True
CELERY_MESSAGE_COMPRESSION = 'gzip'
# internal data format
CELERY_ACCEPT_CONTENT = ['json', 'internal_json']
CELERY_RESULT_SERIALIZER = 'internal_json'
CELERY_TASK_SERIALIZER = 'internal_json'
# beat
CELERYBEAT_LOG_LEVEL = 'WARNING'

# cleanup
del always_eager
del os
