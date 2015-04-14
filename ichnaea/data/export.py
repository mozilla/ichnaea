import requests
from simplejson import dumps
from webob.response import gzip_app_iter

from ichnaea.customjson import kombu_loads
from ichnaea.data.base import DataTask


def queue_length(redis_client, redis_key):
    return redis_client.llen(redis_key)


class ExportScheduler(DataTask):

    def __init__(self, task, session):
        DataTask.__init__(self, task, session)
        self.export_queues = task.app.export_queues

    def queue_length(self, redis_key):
        return queue_length(self.redis_client, redis_key)

    def schedule(self, export_reports):
        triggered = 0
        for name, settings in self.export_queues.items():
            redis_key = settings['redis_key']
            if self.queue_length(redis_key) >= settings['batch']:
                export_reports.delay(name)
                triggered += 1
        return triggered


class ReportExporter(DataTask):

    def __init__(self, task, session, export_name):
        DataTask.__init__(self, task, session)
        self.export_name = export_name
        self.settings = task.app.export_queues[self.export_name]
        self.batch = self.settings['batch']
        self.redis_key = self.settings['redis_key']

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
        reports = [kombu_loads(item) for item in queued_items]
        upload_task.delay(dumps({'items': reports}))

        # check the queue at the end, if there's still enough to do
        # immediately schedule another job
        if self.queue_length() >= self.batch:
            export_task.apply_async(args=[self.export_name], expires=300)

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
