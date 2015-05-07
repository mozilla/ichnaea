from collections import (
    defaultdict,
    namedtuple,
)
from datetime import datetime
import urlparse
import uuid

import boto
import requests
import simplejson
import pytz

from ichnaea.customjson import kombu_dumps
from ichnaea.data.base import DataTask
from ichnaea import util

MetadataGroup = namedtuple('MetadataGroup', 'api_key email ip nickname')


class ExportScheduler(DataTask):

    def __init__(self, task, session):
        DataTask.__init__(self, task, session)
        self.export_queues = task.app.export_queues

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

    def export(self, export_task, upload_task):
        export_queue = self.export_queue
        if not export_queue.enough_data(self.queue_key):  # pragma: no cover
            return 0

        items = export_queue.dequeue(self.queue_key, batch=self.batch)
        if items and len(items) < self.batch:  # pragma: no cover
            # race condition, something emptied the queue in between
            # our llen call and fetching the items, put them back
            export_queue.enqueue(items, self.queue_key)
            return 0

        if self.metadata:  # pragma: no cover
            reports = items
        else:
            # split out metadata
            reports = {'items': [item['report'] for item in items]}

        upload_task.delay(
            self.export_queue_name,
            simplejson.dumps(reports),
            queue_key=self.queue_key)

        # check the queue at the end, if there's still enough to do
        # schedule another job, but give it a second before it runs
        if export_queue.enough_data(self.queue_key):
            export_task.apply_async(
                args=[self.export_queue_name],
                kwargs={'queue_key': self.queue_key},
                countdown=1,
                expires=300)

        return len(items)


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


class InternalUploader(ReportUploader):

    @staticmethod
    def _task():
        # avoiding import cycle problems, sigh!
        from ichnaea.data.tasks import insert_measures
        return insert_measures

    def _format_report(self, item):
        report = {}

        def conditional_set(item, target, value, missing):
            if value != missing:
                item[target] = value

        position_map = [
            ('lat', 'latitude', None),
            ('lon', 'longitude', None),
            ('accuracy', 'accuracy', 0),
            ('altitude', 'altitude', 0),
            ('altitude_accuracy', 'altitudeAccuracy', 0),
            ('age', 'age', None),
            ('heading', 'heading', -1.0),
            ('pressure', 'pressure', None),
            ('speed', 'speed', -1.0),
            ('source', 'source', 'gps'),
        ]

        cell_map = [
            ('radio', 'radioType', None),
            ('mcc', 'mobileCountryCode', -1),
            ('mnc', 'mobileNetworkCode', -1),
            ('lac', 'locationAreaCode', -1),
            ('cid', 'cellId', -1),
            ('age', 'age', None),
            ('asu', 'asu', -1),
            ('psc', 'primaryScramblingCode', -1),
            ('serving', 'serving', None),
            ('signal', 'signalStrength', 0),
            ('ta', 'timingAdvance', 0),
        ]

        wifi_map = [
            ('key', 'macAddress', None),
            ('radio', 'radioType', None),
            ('age', 'age', None),
            ('channel', 'channel', 0),
            ('frequency', 'frequency', 0),
            ('signalToNoiseRatio', 'signalToNoiseRatio', 0),
            ('signal', 'signalStrength', 0),
        ]

        timestamp = item.get('timestamp', None)
        if timestamp:
            dt = datetime.utcfromtimestamp(timestamp / 1000.0)
            report['time'] = dt.replace(microsecond=0, tzinfo=pytz.UTC)

        position = item.get('position')
        if position:
            for target, source, missing in position_map:
                conditional_set(report, target,
                                position.get(source, missing), missing)

        cells = []
        for cell_item in item.get('cellTowers', ()):
            cell = {}
            for target, source, missing in cell_map:
                conditional_set(cell, target,
                                cell_item.get(source, missing), missing)
            if cell:
                cells.append(cell)

        if cells:
            report['cell'] = cells

        wifis = []
        for wifi_item in item.get('wifiAccessPoints', ()):
            wifi = {}
            for target, source, missing in wifi_map:
                conditional_set(wifi, target,
                                wifi_item.get(source, missing), missing)
            if wifi:
                wifis.append(wifi)

        if wifis:
            report['wifi'] = wifis

        if report.get('cell') or report.get('wifi'):
            return report

    def send(self, url, data):
        groups = defaultdict(list)
        for item in simplejson.loads(data):
            group = MetadataGroup(**item['metadata'])
            report = self._format_report(item['report'])
            if report:
                groups[group].append(report)

        for group, reports in groups.items():
            self._task().apply_async(
                kwargs={
                    'api_key_text': group.api_key,
                    'email': group.email,
                    'ip': group.ip,
                    'items': kombu_dumps(reports),
                    'nickname': group.nickname,
                },
                expires=21600)


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
