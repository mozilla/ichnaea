import urlparse

from ichnaea.cache import redis_pipeline
from ichnaea.customjson import (
    kombu_dumps,
    kombu_loads,
)

EXPORT_QUEUE_PREFIX = 'queue_export_'
_sentinel = object()


def configure_data(redis_client):
    data_queues = {
        'update_cellarea': DataQueue('update_cellarea',
                                     queue_key='update_cell_lac',
                                     redis_client=redis_client),
    }
    return data_queues


def configure_export(app_config):
    export_queues = {}
    for section_name in app_config.sections():
        if section_name.startswith('export:'):
            section = app_config.get_map(section_name)
            name = section_name.split(':')[1]
            export_queues[name] = ExportQueue(name, section)
    return export_queues


class DataQueue(object):

    def __init__(self, name, queue_key=None, redis_client=None):
        self.name = name
        self.queue_key = queue_key
        self.redis_client = redis_client

    @property
    def monitor_name(self):
        return self.queue_key

    def dequeue(self, batch=100):
        with self.redis_client.pipeline() as pipe:
            pipe.multi()
            pipe.lrange(self.queue_key, 0, batch - 1)
            pipe.ltrim(self.queue_key, batch, -1)
            result = [kombu_loads(item) for item in pipe.execute()[0]]
        return result

    def _enqueue(self, pipe, data, batch, expire):
        if data and expire:
            pipe.expire(self.queue_key, expire)

        while data:
            pipe.lpush(self.queue_key, *data[:batch])
            data = data[batch:]

    def enqueue(self, items, batch=100, expire=86400, pipe=None):
        data = [str(kombu_dumps(item)) for item in items]
        if pipe is not None:
            self._enqueue(pipe, data, batch, expire)
        else:
            with redis_pipeline(self.redis_client) as pipe:
                self._enqueue(pipe, data, batch, expire)


class ExportQueue(object):

    def __init__(self, name, settings):
        self.name = name
        self.settings = settings
        self.batch = int(settings.get('batch', -1))
        self.metadata = bool(settings.get('metadata', False))
        self.url = settings.get('url', '') or ''
        self.scheme = urlparse.urlparse(self.url).scheme
        self.source_apikey = settings.get('source_apikey', _sentinel)

    @property
    def monitor_name(self):
        if self.scheme == 's3':
            return None
        return self.queue_key()

    def queue_key(self, api_key=None):
        if self.scheme == 's3':
            if not api_key:
                api_key = 'no_key'
            return self.queue_prefix + api_key
        return EXPORT_QUEUE_PREFIX + self.name

    @property
    def queue_prefix(self):
        if self.scheme == 's3':
            return EXPORT_QUEUE_PREFIX + self.name + ':'
        return None

    def export_allowed(self, api_key):
        return (api_key != self.source_apikey)
