import requests
from simplejson import dumps

from ichnaea.customjson import kombu_loads
from ichnaea.data.base import DataTask
from ichnaea.util import encode_gzip


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
        for name, settings in self.export_queues.items():
            redis_key = settings['redis_key']
            if self.queue_length(redis_key) >= settings['batch']:
                export_task.delay(name)
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
        items = [kombu_loads(item) for item in queued_items]
        # split out metadata
        reports = [item['report'] for item in items]

        upload_task.delay(self.export_name, dumps({'items': reports}))

        # check the queue at the end, if there's still enough to do
        # immediately schedule another job
        if self.queue_length() >= self.batch:
            export_task.apply_async(args=[self.export_name], expires=300)

        return len(queued_items)


class ReportUploader(DataTask):

    def __init__(self, task, session, export_name):
        DataTask.__init__(self, task, session)
        self.export_name = export_name
        self.settings = task.app.export_queues[self.export_name]
        self.url = self.settings['url']

    def upload(self, data):
        if self.url is None:
            return False
        return self.send(self.url, data)

    def send(self, url, data):
        stats_client = self.stats_client
        stats_prefix = 'items.export.%s.' % self.export_name

        headers = {
            'Content-Encoding': 'gzip',
            'Content-Type': 'application/json',
            'User-Agent': 'ichnaea',
        }

        with stats_client.timer(stats_prefix + 'upload'):
            response = requests.post(
                url,
                data=encode_gzip(data),
                headers=headers,
                timeout=60.0,
                verify=False,  # TODO switch this back on
            )

        # log upload_status and trigger exception for bad responses
        # this causes the task to be re-tried
        response_code = response.status_code
        stats_client.incr('%supload_status.%s' % (stats_prefix, response_code))
        response.raise_for_status()

        # only log successful uploads
        stats_client.incr(stats_prefix + 'batches')
        return True
