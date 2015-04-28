import urlparse
import uuid

import boto
import requests
from simplejson import dumps

from ichnaea.customjson import kombu_loads
from ichnaea.data.base import DataTask
from ichnaea import util


def queue_length(redis_client, queue_key):
    return redis_client.llen(queue_key)


class ExportScheduler(DataTask):

    def __init__(self, task, session):
        DataTask.__init__(self, task, session)
        self.export_queues = task.app.export_queues

    def queue_length(self, queue_key):
        return queue_length(self.redis_client, queue_key)

    def schedule(self, export_task):
        triggered = 0
        for export_queue in self.export_queues.values():
            if not export_queue.queue_prefix:
                triggered += self.schedule_one(export_queue, export_task)
            else:
                triggered += self.schedule_multiple(export_queue, export_task)
        return triggered

    def schedule_one(self, export_queue, export_task):
        triggered = 0
        queue_key = export_queue.queue_key()
        if self.queue_length(queue_key) >= export_queue.batch:
            export_task.delay(export_queue.name)
            triggered += 1
        return triggered

    def schedule_multiple(self, export_queue, export_task):
        triggered = 0
        queue_prefix = export_queue.queue_prefix
        for queue_key in self.redis_client.scan_iter(match=queue_prefix + '*',
                                                     count=100):
            if self.queue_length(queue_key) >= export_queue.batch:
                export_task.delay(export_queue.name, queue_key=queue_key)
                triggered += 1
        return triggered


class ReportExporter(DataTask):

    def __init__(self, task, session, export_queue_name, queue_key):
        DataTask.__init__(self, task, session)
        self.export_queue_name = export_queue_name
        self.export_queue = task.app.export_queues[export_queue_name]
        self.batch = self.export_queue.batch
        self.metadata = self.export_queue.metadata
        self.queue_key = queue_key
        if not self.queue_key:
            self.queue_key = self.export_queue.queue_key()

    def queue_length(self):
        return queue_length(self.redis_client, self.queue_key)

    def dequeue_reports(self):
        pipe = self.redis_client.pipeline()
        pipe.multi()
        pipe.lrange(self.queue_key, 0, self.batch - 1)
        pipe.ltrim(self.queue_key, self.batch, -1)
        return pipe.execute()[0]

    def export(self, export_task, upload_task):
        length = self.queue_length()
        if length < self.batch:  # pragma: no cover
            # not enough to do, skip
            return 0

        queued_items = self.dequeue_reports()
        if queued_items and len(queued_items) < self.batch:  # pragma: no cover
            # race condition, something emptied the queue in between
            # our llen call and fetching the items, put them back
            self.redis_client.lpush(self.queue_key, *queued_items)
            return 0

        # schedule the upload task
        items = [kombu_loads(item) for item in queued_items]

        if self.metadata:  # pragma: no cover
            reports = items
        else:
            # split out metadata
            reports = {'items': [item['report'] for item in items]}

        upload_task.delay(
            self.export_queue_name,
            dumps(reports),
            queue_key=self.queue_key)

        # check the queue at the end, if there's still enough to do
        # schedule another job, but give it a second before it runs
        if self.queue_length() >= self.batch:
            export_task.apply_async(
                args=[self.export_queue_name],
                kwargs={'queue_key': self.queue_key},
                countdown=1,
                expires=300)

        return len(queued_items)


class ReportUploader(DataTask):

    def __init__(self, task, session, export_queue_name, queue_key):
        DataTask.__init__(self, task, session)
        self.export_queue_name = export_queue_name
        self.export_queue = task.app.export_queues[export_queue_name]
        self.stats_prefix = 'items.export.%s.' % export_queue_name
        self.url = self.export_queue.url
        self.queue_key = queue_key
        if not self.queue_key:  # pragma: no cover
            self.queue_key = self.export_queue.queue_key()

    def upload(self, data):
        result = self.send(self.url, data)
        self.stats_client.incr(self.stats_prefix + 'batches')
        return result

    def send(self, url, data):  # pragma: no cover
        raise NotImplementedError


class GeosubmitUploader(ReportUploader):

    def send(self, url, data):
        headers = {
            'Content-Encoding': 'gzip',
            'Content-Type': 'application/json',
            'User-Agent': 'ichnaea',
        }
        with self.stats_client.timer(self.stats_prefix + 'upload'):
            response = requests.post(
                url,
                data=util.encode_gzip(data),
                headers=headers,
                timeout=60.0,
                verify=False,  # TODO switch this back on
            )

        # log upload_status and trigger exception for bad responses
        # this causes the task to be re-tried
        response_code = response.status_code
        self.stats_client.incr(
            '%supload_status.%s' % (self.stats_prefix, response_code))
        response.raise_for_status()
        return True


class S3Uploader(ReportUploader):

    def __init__(self, task, session, export_queue_name, queue_key):
        super(S3Uploader, self).__init__(
            task, session, export_queue_name, queue_key)
        self.export_queue_name = export_queue_name
        self.export_queue = task.app.export_queues[export_queue_name]
        _, self.bucket, path = urlparse.urlparse(self.url)[:3]
        # s3 key names start without a leading slash
        path = path.lstrip('/')
        if not path.endswith('/'):
            path += '/'
        self.path = path

    def send(self, url, data):
        year, month, day = util.utcnow().timetuple()[:3]
        # strip away queue prefix again
        api_key = self.queue_key
        queue_prefix = self.export_queue.queue_prefix
        if self.queue_key.startswith(queue_prefix):
            api_key = self.queue_key[len(queue_prefix):]

        key_name = self.path.format(
            api_key=api_key, year=year, month=month, day=day)
        key_name += uuid.uuid1().hex + '.json.gz'

        try:
            with self.stats_client.timer(self.stats_prefix + 'upload'):
                conn = boto.connect_s3()
                bucket = conn.get_bucket(self.bucket)
                key = boto.s3.key.Key(bucket)
                key.key = key_name
                key.content_encoding = 'gzip'
                key.content_type = 'application/json'
                key.set_contents_from_string(util.encode_gzip(data))
                key.close()

            self.stats_client.incr(
                '%supload_status.success' % self.stats_prefix)
            return True
        except Exception:  # pragma: no cover
            self.raven_client.captureException()

            self.stats_client.incr(
                '%supload_status.failure' % self.stats_prefix)
            return False
