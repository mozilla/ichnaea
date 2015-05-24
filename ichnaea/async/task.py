from celery import Task
from kombu.serialization import (
    dumps as kombu_dumps,
    loads as kombu_loads,
)

from ichnaea.cache import redis_pipeline
from ichnaea.db import db_worker_session


class DatabaseTask(Task):
    abstract = True
    acks_late = False
    ignore_result = True
    max_retries = 3

    _auto_retry = True
    _shortname = None

    @property
    def shortname(self):
        short = self._shortname
        if short is None:
            # strip off ichnaea prefix and tasks module
            segments = self.name.split('.')
            segments = [s for s in segments if s not in ('ichnaea', 'tasks')]
            short = self._shortname = '.'.join(segments)
        return short

    def __call__(self, *args, **kw):
        with self.stats_client.timer('task.' + self.shortname):
            try:
                result = super(DatabaseTask, self).__call__(*args, **kw)
            except Exception as exc:
                self.raven_client.captureException()
                if self._auto_retry and not self.app.conf.CELERY_ALWAYS_EAGER:
                    raise self.retry(exc=exc)  # pragma: no cover
                raise
        return result

    def apply(self, *args, **kw):
        # This method is only used when calling tasks directly and blocking
        # on them. It's also used if always_eager is set, like in tests.
        # Using this in real code should be rare, so the extra overhead of
        # the check shouldn't matter.

        if self.app.conf.CELERY_ALWAYS_EAGER:
            # We do the extra check to make sure this was really used from
            # inside tests

            # We feed the task arguments through the de/serialization process
            # to make sure the arguments can indeed be serialized.
            serializer = self.app.conf.CELERY_TASK_SERIALIZER
            content_type, encoding, data = kombu_dumps(args, serializer)
            args = kombu_loads(data, content_type, encoding)

        return super(DatabaseTask, self).apply(*args, **kw)

    def redis_pipeline(self, execute=True):
        # returns a context manager
        return redis_pipeline(self.redis_client, execute=execute)

    def db_session(self, commit=True):
        # returns a context manager
        return db_worker_session(self.app.db_rw, commit=commit)

    @property
    def geoip_db(self):  # pragma: no cover
        return self.app.geoip_db

    @property
    def raven_client(self):
        return self.app.raven_client

    @property
    def redis_client(self):
        return self.app.redis_client

    @property
    def stats_client(self):
        return self.app.stats_client
