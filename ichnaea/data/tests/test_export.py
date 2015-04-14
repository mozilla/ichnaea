import time

from requests.exceptions import ConnectionError
from simplejson import dumps

from ichnaea.async.config import EXPORT_QUEUE_PREFIX
from ichnaea.data.export import queue_length
from ichnaea.data.tasks import (
    schedule_export_reports,
    queue_reports,
    upload_reports,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)


class BaseTest(object):

    def add_reports(self, number=3, api_key='test'):
        reports = []
        for i in range(number):
            report = {
                'timestamp': time.time() * 1000.0,
                'position': {},
                'cellTowers': [],
                'wifiAccessPoints': [],
            }
            cell = CellFactory.build()
            report['position']['latitude'] = cell.lat
            report['position']['longitude'] = cell.lon
            report['position']['accuracy'] = 17 + i
            cell_data = {
                'radioType': cell.radio.name,
                'mobileCountryCode': cell.mcc,
                'mobileNetworkCode': cell.mnc,
                'locationAreaCode': cell.lac,
                'cellId': cell.cid,
                'primaryScramblingCode': cell.psc,
                'signalStrength': -110 + i,
            }
            report['cellTowers'].append(cell_data)
            wifis = WifiFactory.build_batch(2, lat=cell.lat, lon=cell.lon)
            for wifi in wifis:
                wifi_data = {
                    'macAddress': wifi.key,
                    'signalStrength': -90 + i,
                }
                report['wifiAccessPoints'].append(wifi_data)
            reports.append(report)

        queue_reports.delay(reports=reports, api_key=api_key).get()

    def queue_length(self, redis_key):
        return queue_length(self.redis_client, redis_key)


class TestExportScheduler(BaseTest, CeleryTestCase):

    def test_schedule_exports(self):
        pass


class TestExporter(BaseTest, CeleryTestCase):

    def setUp(self):
        super(TestExporter, self).setUp()
        self.celery_app.export_queues = {
            'test': {
                'url': 'http://localhost:7001/v2/geosubmit?key=external',
                'source_apikey': 'export_source',
                'batch': 3,
                'redis_key': EXPORT_QUEUE_PREFIX + 'test',
            },
            'everything': {
                'url': 'http://localhost:7001/v2/geosubmit?key=external',
                'batch': 5,
                'redis_key': EXPORT_QUEUE_PREFIX + 'everything',
            },
            'no_test': {
                'url': 'http://localhost:7001/v2/geosubmit?key=external',
                'source_apikey': 'test',
                'batch': 2,
                'redis_key': EXPORT_QUEUE_PREFIX + 'no_test',
            },
        }
        self.prefix = EXPORT_QUEUE_PREFIX

    def test_enqueue_reports(self):
        self.add_reports(4)
        self.add_reports(1, api_key='test2')
        expected = [
            (EXPORT_QUEUE_PREFIX + 'test', 5),
            (EXPORT_QUEUE_PREFIX + 'everything', 5),
            (EXPORT_QUEUE_PREFIX + 'no_test', 1),
        ]
        for key, num in expected:
            self.assertEqual(self.queue_length(key), num)

    def test_one_queue(self):
        self.add_reports(3)
        triggered = schedule_export_reports.delay().get()
        self.assertEqual(triggered, 1)
        # data from one queue was processed
        expected = [
            (EXPORT_QUEUE_PREFIX + 'test', 0),
            (EXPORT_QUEUE_PREFIX + 'everything', 3),
            (EXPORT_QUEUE_PREFIX + 'no_test', 0),
        ]
        for key, num in expected:
            self.assertEqual(self.queue_length(key), num)

    def test_one_batch(self):
        self.add_reports(5)
        schedule_export_reports.delay().get()
        self.assertEqual(self.queue_length(EXPORT_QUEUE_PREFIX + 'test'), 2)

    def test_multiple_batches(self):
        self.add_reports(10)
        schedule_export_reports.delay().get()
        self.assertEqual(self.queue_length(EXPORT_QUEUE_PREFIX + 'test'), 1)


class TestUploader(BaseTest, CeleryTestCase):

    def test_upload(self):
        reports = self.add_reports(2)
        data = dumps({'items': reports})

        exc = None
        try:
            upload_reports.delay(data, url='http://127.0.0.1:9').get()
        except Exception as exc:
            pass
        self.assertTrue(isinstance(exc, ConnectionError), exc)
