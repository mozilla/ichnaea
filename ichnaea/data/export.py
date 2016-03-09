from collections import defaultdict
import re

import simplejson
from six.moves.urllib.parse import urlparse

from ichnaea.queue import DataQueue

WHITESPACE = re.compile('\s', flags=re.UNICODE)


class ExportQueue(object):
    """
    A Redis based queue which stores binary or JSON encoded items
    in lists. The queue supports dynamic queue keys and partitioned
    queues with a common queue key prefix.

    The lists maintain a TTL value corresponding to the time data has
    been last put into the queue.
    """

    metadata = False

    def __init__(self, key, redis_client,
                 url=None, batch=0, skip_keys=(),
                 uploader_type=None, compress=False):
        self.key = key
        self.redis_client = redis_client
        self.batch = batch
        self.url = url
        self.skip_keys = skip_keys
        self.uploader_type = uploader_type
        self.compress = compress

    def _data_queue(self, queue_key):
        return DataQueue(queue_key, self.redis_client,
                         batch=self.batch, compress=self.compress, json=True)

    @classmethod
    def configure_queue(cls, key, redis_client, settings, compress=False):
        from ichnaea.data import upload
        from ichnaea.data.internal import InternalUploader

        url = settings.get('url', '') or ''
        scheme = urlparse(url).scheme
        batch = int(settings.get('batch', 0))

        skip_keys = WHITESPACE.split(settings.get('skip_keys', ''))
        skip_keys = tuple([skip_key for skip_key in skip_keys if skip_key])

        queue_types = {
            'http': (HTTPSExportQueue, upload.GeosubmitUploader),
            'https': (HTTPSExportQueue, upload.GeosubmitUploader),
            'internal': (InternalExportQueue, InternalUploader),
            's3': (S3ExportQueue, upload.S3Uploader),
        }
        klass, uploader_type = queue_types.get(scheme, (cls, None))

        return klass(key, redis_client,
                     url=url, batch=batch, skip_keys=skip_keys,
                     uploader_type=uploader_type, compress=compress)

    def dequeue(self, queue_key):
        return self._data_queue(queue_key).dequeue()

    def enqueue(self, items, queue_key, pipe=None):
        self._data_queue(queue_key).enqueue(items, pipe=pipe)

    def export_allowed(self, api_key):
        return (api_key not in self.skip_keys)

    def metric_tag(self):
        # strip away queue_export_ prefix
        return self.key[13:]

    @property
    def monitor_name(self):
        return self.key

    def queue_key(self, api_key=None):
        return self.key

    def ready(self, queue_key=None):
        if queue_key is None:
            queue_key = self.key
        return self._data_queue(queue_key).ready()

    def size(self, queue_key):
        return self.redis_client.llen(queue_key)


class HTTPSExportQueue(ExportQueue):
    pass


class InternalExportQueue(ExportQueue):

    metadata = True


class S3ExportQueue(ExportQueue):

    @property
    def monitor_name(self):
        return None

    def partitions(self):
        # e.g. ['queue_export_something:api_key']
        return self.redis_client.scan_iter(match=self.key + ':*', count=100)

    def queue_key(self, api_key=None):
        if not api_key:
            api_key = 'no_key'
        return self.key + ':' + api_key


class ExportScheduler(object):

    def __init__(self, task):
        self.task = task
        self.redis_client = task.redis_client
        self.export_queues = task.app.export_queues

    def __call__(self, export_task):
        triggered = 0
        for export_queue in self.export_queues.values():
            if isinstance(export_queue, S3ExportQueue):
                triggered += self.schedule_multiple(export_queue, export_task)
            else:
                triggered += self.schedule_one(export_queue, export_task)
        return triggered

    def schedule_one(self, export_queue, export_task):
        triggered = 0
        if export_queue.ready():
            export_task.delay(export_queue.key)
            triggered += 1
        return triggered

    def schedule_multiple(self, export_queue, export_task):
        triggered = 0
        for queue_key in export_queue.partitions():
            if export_queue.ready(queue_key):
                export_task.delay(export_queue.key, queue_key=queue_key)
                triggered += 1
        return triggered


class IncomingQueue(object):

    def __init__(self, task, pipe):
        self.task = task
        self.pipe = pipe
        self.data_queue = task.app.data_queues['update_incoming']
        self.export_queues = task.app.export_queues

    def __call__(self, batch=100):
        data = self.data_queue.dequeue(batch=batch)
        if not data:
            return

        grouped = defaultdict(list)
        for item in data:
            grouped[item['api_key']].append({
                'api_key': item['api_key'],
                'nickname': item['nickname'],
                'report': item['report'],
            })

        for api_key, items in grouped.items():
            for queue in self.export_queues.values():
                if queue.export_allowed(api_key):
                    queue_key = queue.queue_key(api_key)
                    queue.enqueue(items, queue_key, pipe=self.pipe)

        if self.data_queue.ready(batch=batch):  # pragma: no cover
            self.task.apply_async(
                kwargs={'batch': batch},
                countdown=2,
                expires=5)


class ReportExporter(object):

    def __init__(self, task, export_queue_key, queue_key):
        self.task = task
        self.export_queue_key = export_queue_key
        self.export_queue = task.app.export_queues[export_queue_key]
        self.metadata = self.export_queue.metadata
        self.queue_key = queue_key
        if not self.queue_key:
            self.queue_key = self.export_queue.queue_key()

    def __call__(self, upload_task):
        items = self.export_queue.dequeue(self.queue_key)
        if not items:  # pragma: no cover
            return

        reports = items
        if not self.metadata:
            # ignore metadata
            reports = {'items': [item['report'] for item in items]}

        upload_task.delay(
            self.export_queue_key,
            simplejson.dumps(reports),
            queue_key=self.queue_key)

        # check the queue at the end, if there's still enough to do
        # schedule another job, but give it a second before it runs
        if self.export_queue.ready(self.queue_key):
            self.task.apply_async(
                args=[self.export_queue_key],
                kwargs={'queue_key': self.queue_key},
                countdown=1,
                expires=300)
