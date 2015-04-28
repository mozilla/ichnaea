import urlparse
import uuid

import boto
import requests
from simplejson import dumps

from ichnaea.customjson import kombu_loads
from ichnaea.data.base import DataTask
from ichnaea import util


def queue_length(redis_client, redis_key):
    return redis_client.llen(redis_key)


class ExportScheduler(DataTask):

    def __init__(self, task, session):
        DataTask.__init__(self, task, session)
        self.export_queues = task.app.export_queues

    def queue_length(self, redis_key):
        return queue_length(self.redis_client, redis_key)

    def schedule(self, export_task):
        triggered = 0
        for name, export_queue in self.export_queues.items():
            redis_key = export_queue.redis_key
            if self.queue_length(redis_key) >= export_queue.batch:
                export_task.delay(name)
                triggered += 1
        return triggered


class ReportExporter(DataTask):

    def __init__(self, task, session, export_name):
        DataTask.__init__(self, task, session)
        self.export_name = export_name
        self.export_queue = task.app.export_queues[export_name]
        self.batch = self.export_queue.batch
        self.redis_key = self.export_queue.redis_key

    def queue_length(self):
        return queue_length(self.redis_client, self.redis_key)

    def dequeue_reports(self):
        pipe = self.redis_client.pipeline()
        pipe.multi()
        pipe.lrange(self.redis_key, 0, self.batch - 1)
        pipe.ltrim(self.redis_key, self.batch, -1)
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
            self.redis_client.lpush(self.redis_key, *queued_items)
            return 0

        # schedule the upload task
        items = [kombu_loads(item) for item in queued_items]
        # split out metadata
        reports = [item['report'] for item in items]

        upload_task.delay(self.export_name, dumps({'items': reports}))

        # check the queue at the end, if there's still enough to do
        # schedule another job, but give it a second before it runs
        if self.queue_length() >= self.batch:
            export_task.apply_async(
                args=[self.export_name],
                countdown=1,
                expires=300)

        return len(queued_items)


class ReportUploader(DataTask):

    def __init__(self, task, session, export_name):
        DataTask.__init__(self, task, session)
        self.export_name = export_name
        self.export_queue = task.app.export_queues[export_name]
        self.stats_prefix = 'items.export.%s.' % export_name
        self.url = self.export_queue.url

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

    def __init__(self, task, session, export_name):
        super(S3Uploader, self).__init__(task, session, export_name)
        _, self.bucket, path = urlparse.urlparse(self.url)[:3]
        # s3 key names start without a leading slash
        path = path.lstrip('/')
        if not path.endswith('/'):
            path += '/'
        self.path = path

    def send(self, url, data):
        year, month, day = util.utcnow().timetuple()[:3]
        key_name = self.path.format(year=year, month=month, day=day)
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
