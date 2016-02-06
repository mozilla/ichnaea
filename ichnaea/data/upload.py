from contextlib import closing
import uuid

import boto
import requests
from six.moves.urllib.parse import urlparse

from ichnaea.data.base import DataTask
from ichnaea import util


class BaseReportUploader(DataTask):

    def __init__(self, task, session, export_queue_name, queue_key):
        DataTask.__init__(self, task, session)
        self.export_queue_name = export_queue_name
        self.export_queue = task.app.export_queues[export_queue_name]
        self.stats_prefix = 'data.export.'
        self.stats_tags = ['key:%s' % export_queue_name]
        self.url = self.export_queue.url
        self.queue_key = queue_key
        if not self.queue_key:  # pragma: no cover
            self.queue_key = self.export_queue.queue_key()

    def __call__(self, data):
        self.send(self.url, data)
        self.stats_client.incr(
            self.stats_prefix + 'batch', tags=self.stats_tags)

    def send(self, url, data):
        raise NotImplementedError()


class GeosubmitUploader(BaseReportUploader):

    def send(self, url, data):
        headers = {
            'Content-Encoding': 'gzip',
            'Content-Type': 'application/json',
            'User-Agent': 'ichnaea',
        }
        with self.stats_client.timed(self.stats_prefix + 'upload',
                                     tags=self.stats_tags):
            response = requests.post(
                url,
                data=util.encode_gzip(data, compresslevel=5),
                headers=headers,
                timeout=60.0,
            )

        # log upload_status and trigger exception for bad responses
        # this causes the task to be re-tried
        self.stats_client.incr(
            self.stats_prefix + 'upload',
            tags=self.stats_tags + ['status:%s' % response.status_code])
        response.raise_for_status()


class S3Uploader(BaseReportUploader):

    def __init__(self, task, session, export_queue_name, queue_key):
        super(S3Uploader, self).__init__(
            task, session, export_queue_name, queue_key)
        self.export_queue_name = export_queue_name
        self.export_queue = task.app.export_queues[export_queue_name]
        _, self.bucket, path = urlparse(self.url)[:3]
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
            with self.stats_client.timed(self.stats_prefix + 'upload',
                                         tags=self.stats_tags):
                conn = boto.connect_s3()
                bucket = conn.get_bucket(self.bucket)
                with closing(boto.s3.key.Key(bucket)) as key:
                    key.key = key_name
                    key.content_encoding = 'gzip'
                    key.content_type = 'application/json'
                    key.set_contents_from_string(
                        util.encode_gzip(data, compresslevel=7))

            self.stats_client.incr(
                self.stats_prefix + 'upload',
                tags=self.stats_tags + ['status:success'])
        except Exception:  # pragma: no cover
            self.raven_client.captureException()
            self.stats_client.incr(
                self.stats_prefix + 'upload',
                tags=self.stats_tags + ['status:failure'])
