"""
Contains a Celery base task.
"""

from celery import Task
from kombu.serialization import (
    dumps as kombu_dumps,
    loads as kombu_loads,
)

from ichnaea.cache import redis_pipeline
from ichnaea.db import db_worker_session


class BaseTask(Task):
    """A base task giving access to various outside connections."""

    abstract = True  #:
    acks_late = False  #:
    countdown = None  #:
    ignore_result = True  #:
    max_retries = 3  #:

    _auto_retry = True  #:
    _shortname = None  #:

    @property
    def shortname(self):
        """
        A short name for the task, used in statsd metric names.
        """
        short = self._shortname
        if short is None:
            # strip off ichnaea prefix and tasks module
            segments = self.name.split('.')
            segments = [s for s in segments if s not in ('ichnaea', 'tasks')]
            short = self._shortname = '.'.join(segments)
        return short

    def __call__(self, *args, **kw):
        """
        Execute the task, capture a statsd timer for the task duration and
        automatically report exceptions into Sentry.
        """
        with self.stats_client.timed('task', tags=['task:' + self.shortname]):
            try:
                result = super(BaseTask, self).__call__(*args, **kw)
            except Exception as exc:  # pragma: no cover
                self.raven_client.captureException()
                if self._auto_retry and not self.app.conf.CELERY_ALWAYS_EAGER:
                    raise self.retry(exc=exc)
                raise
        return result

    def apply(self, *args, **kw):
        """
        This method is only used when calling tasks directly and blocking
        on them. It's also used if always_eager is set, like in tests.

        If always_eager is set, we feed the task arguments through the
        de/serialization process to make sure the arguments can indeed
        be serialized into JSON.
        """

        if self.app.conf.CELERY_ALWAYS_EAGER:
            # We do the extra check to make sure this was really used from
            # inside tests
            serializer = self.app.conf.CELERY_TASK_SERIALIZER
            content_type, encoding, data = kombu_dumps(args, serializer)
            args = kombu_loads(data, content_type, encoding)

        return super(BaseTask, self).apply(*args, **kw)

    def apply_countdown(self, args=None, kwargs=None):
        """
        Run the task again after the task's default countdown.
        """
        self.apply_async(countdown=self.countdown, args=args, kwargs=kwargs)

    def db_session(self, commit=True):
        """
        Returns a database session usable as a context manager.

        :param commit: Should the session be committed or aborted at the end?
        :type commit: bool
        """
        return db_worker_session(self.app.db_rw, commit=commit)

    def redis_pipeline(self, execute=True):
        """
        Returns a Redis pipeline usable as a context manager.

        :param execute: Should the pipeline be executed or aborted at the end?
        :type execute: bool
        """
        return redis_pipeline(self.redis_client, execute=execute)

    @property
    def geoip_db(self):  # pragma: no cover
        """Exposes a :class:`~ichnaea.geoip.GeoIPWrapper`."""
        return self.app.geoip_db

    @property
    def raven_client(self):  # pragma: no cover
        """Exposes a :class:`~raven.Client`."""
        return self.app.raven_client

    @property
    def redis_client(self):
        """Exposes a :class:`~ichnaea.cache.RedisClient`."""
        return self.app.redis_client

    @property
    def stats_client(self):
        """Exposes a :class:`~ichnaea.log.StatsClient`."""
        return self.app.stats_client
