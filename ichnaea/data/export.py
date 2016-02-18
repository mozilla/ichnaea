from collections import defaultdict

import simplejson

from ichnaea.data.base import DataTask


class ExportScheduler(DataTask):

    def __init__(self, task, session):
        DataTask.__init__(self, task, session)
        self.export_queues = task.app.export_queues

    def __call__(self, export_task):
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
        if export_queue.enough_data(queue_key):
            export_task.delay(export_queue.name)
            triggered += 1
        return triggered

    def schedule_multiple(self, export_queue, export_task):
        triggered = 0
        queue_prefix = export_queue.queue_prefix
        for queue_key in self.redis_client.scan_iter(match=queue_prefix + '*',
                                                     count=100):
            if export_queue.enough_data(queue_key):
                export_task.delay(export_queue.name, queue_key=queue_key)
                triggered += 1
        return triggered


class IncomingQueue(DataTask):

    def __init__(self, task, session, pipe):
        DataTask.__init__(self, task, session)
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
            for name, queue in self.export_queues.items():
                if queue.export_allowed(api_key):
                    queue_key = queue.queue_key(api_key)
                    queue.enqueue(items, queue_key, pipe=self.pipe)

        if self.data_queue.enough_data(batch=batch):  # pragma: no cover
            self.task.apply_async(
                kwargs={'batch': batch},
                countdown=2,
                expires=5)


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

    def __call__(self, upload_task):
        export_queue = self.export_queue
        if not export_queue.enough_data(self.queue_key):  # pragma: no cover
            return

        items = export_queue.dequeue(self.queue_key, batch=self.batch)
        if items and len(items) < self.batch:  # pragma: no cover
            # race condition, something emptied the queue in between
            # our llen call and fetching the items, put them back
            export_queue.enqueue(items, self.queue_key)
            return

        reports = items
        if not self.metadata:
            # ignore metadata
            reports = {'items': [item['report'] for item in items]}

        upload_task.delay(
            self.export_queue_name,
            simplejson.dumps(reports),
            queue_key=self.queue_key)

        # check the queue at the end, if there's still enough to do
        # schedule another job, but give it a second before it runs
        if export_queue.enough_data(self.queue_key):
            self.task.apply_async(
                args=[self.export_queue_name],
                kwargs={'queue_key': self.queue_key},
                countdown=1,
                expires=300)
