import requests
from simplejson import dumps
from webob.response import gzip_app_iter

from ichnaea.customjson import kombu_loads
from ichnaea.data.base import DataTask
from ichnaea.data.queue import QUEUE_EXPORT_KEY


def check_queue_length(redis_client):
    return redis_client.llen(QUEUE_EXPORT_KEY)


def enqueue_reports(redis_client, items):
    if items:
        redis_client.lpush(QUEUE_EXPORT_KEY, *items)


class ReportExporter(DataTask):

    def check_queue_length(self):
        return check_queue_length(self.redis_client)

    def dequeue_reports(self, batch=1000):
        pipe = self.redis_client.pipeline()
        pipe.multi()
        pipe.lrange(QUEUE_EXPORT_KEY, 0, batch - 1)
        pipe.ltrim(QUEUE_EXPORT_KEY, batch, -1)
        return pipe.execute()[0]

    def export(self, export_task, upload_task, batch=1000):
        queue_length = self.check_queue_length()
        if queue_length < batch:
            # not enough to do, skip
            return 0

        queued_items = self.dequeue_reports(batch=batch)
        if len(queued_items) < batch:  # pragma: no cover
            # race condition, something emptied the queue in between
            # our llen call and fetching the items, put them back
            enqueue_reports(self.redis_client, queued_items)
            return 0

        # schedule the upload task
        reports = [kombu_loads(item) for item in queued_items]
        upload_task.delay(dumps({'items': reports}))

        # check the queue at the end, if there's still enough to do
        # immediately schedule another job
        if self.check_queue_length() >= batch:
            export_task.apply_async(kwargs={'batch': batch}, expires=300)

        return len(queued_items)


class ReportUploader(DataTask):

    def __init__(self, task, session, url=None):
        DataTask.__init__(self, task, session)
        self.url = url

    def upload(self, data):
        if self.url is None:
            return False

        headers = {
            'Content-Encoding': 'gzip',
            'Content-Type': 'application/json',
        }

        return self.send(self.url, ''.join(gzip_app_iter(data)), headers)

    def send(self, url, data, headers):  # pragma: no cover
        response = requests.post(
            url,
            data=data,
            headers=headers,
            timeout=60.0,
            verify=False,  # TODO switch this back on
        )

        # trigger exception for bad responses
        # this causes the task to be re-tried
        response.raise_for_status()

        return response.status_code == requests.codes.ok
