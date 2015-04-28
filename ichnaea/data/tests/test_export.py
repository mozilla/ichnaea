from contextlib import contextmanager
import json
import time

import boto
from celery.exceptions import Retry
import mock
import requests_mock

from ichnaea.async.queues import configure_export
from ichnaea.config import DummyConfig
from ichnaea.data.export import queue_length
from ichnaea.data.tasks import (
    schedule_export_reports,
    queue_reports,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)
from ichnaea import util


@contextmanager
def mock_s3():
    mock_conn = mock.MagicMock()
    mock_key = mock.MagicMock()
    with mock.patch.object(boto, 'connect_s3', mock_conn):
        with mock.patch('boto.s3.key.Key', lambda _: mock_key):
            yield mock_key


class BaseTest(object):

    def add_reports(self, number=3, api_key='test', email=None):
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

        queue_reports.delay(
            reports=reports, api_key=api_key, email=email).get()
        return reports

    def queue_length(self, redis_key):
        return queue_length(self.redis_client, redis_key)


class TestExporter(BaseTest, CeleryTestCase):

    def setUp(self):
        super(TestExporter, self).setUp()
        config = DummyConfig({
            'export:test': {
                'url': None,
                'source_apikey': 'export_source',
                'batch': '3',
            },
            'export:everything': {
                'url': '',
                'batch': '5',
            },
            'export:no_test': {
                'source_apikey': 'test',
                'batch': '2',
            },
            'export:invalid_ftp': {
                'url': 'ftp://127.0.0.1:9/',
                'batch': '5',
            },
            'export:invalid': {
                'url': 'no_url',
                'batch': '5',
            },
        })
        self.celery_app.export_queues = queues = configure_export(config)
        self.test_queue_key = queues['test'].queue_key()

    def test_enqueue_reports(self):
        self.add_reports(3)
        self.add_reports(1, api_key='test2')
        self.add_reports(1, api_key=None)

        export_queues = self.celery_app.export_queues
        expected = [
            (export_queues['test'].queue_key(), 5),
            (export_queues['everything'].queue_key(), 5),
            (export_queues['no_test'].queue_key(), 2),
        ]
        for key, num in expected:
            self.assertEqual(self.queue_length(key), num)

    def test_one_queue(self):
        self.add_reports(3)
        triggered = schedule_export_reports.delay().get()
        self.assertEqual(triggered, 1)

        # data from one queue was processed
        export_queues = self.celery_app.export_queues
        expected = [
            (export_queues['test'].queue_key(), 0),
            (export_queues['everything'].queue_key(), 3),
            (export_queues['no_test'].queue_key(), 0),
        ]
        for key, num in expected:
            self.assertEqual(self.queue_length(key), num)

    def test_one_batch(self):
        self.add_reports(5)
        schedule_export_reports.delay().get()
        self.assertEqual(self.queue_length(self.test_queue_key), 2)

    def test_multiple_batches(self):
        self.add_reports(10)
        schedule_export_reports.delay().get()
        self.assertEqual(self.queue_length(self.test_queue_key), 1)


class TestGeosubmitUploader(BaseTest, CeleryTestCase):

    def setUp(self):
        super(TestGeosubmitUploader, self).setUp()
        config = DummyConfig({
            'export:test': {
                'url': 'http://127.0.0.1:9/v2/geosubmit?key=external',
                'batch': '3',
            },
        })
        self.celery_app.export_queues = configure_export(config)

    def test_upload(self):
        reports = []
        reports.extend(self.add_reports(1, email='secretemail@localhost'))
        reports.extend(self.add_reports(1, api_key='e5444e9f-7946'))
        reports.extend(self.add_reports(1, api_key=None))

        with requests_mock.Mocker() as mock:
            mock.register_uri('POST', requests_mock.ANY, text='{}')
            schedule_export_reports.delay().get()

        self.assertEqual(mock.call_count, 1)
        req = mock.request_history[0]

        # check headers
        self.assertEqual(req.headers['Content-Type'], 'application/json')
        self.assertEqual(req.headers['Content-Encoding'], 'gzip')
        self.assertEqual(req.headers['User-Agent'], 'ichnaea')

        # check body
        body = util.decode_gzip(req.body)
        # make sure we don't accidentally leak emails
        self.assertFalse('secretemail' in body)

        # make sure a standards based json can decode this data
        # and none of our internal_json structures end up in it
        send_reports = json.loads(body)['items']
        self.assertEqual(len(send_reports), 3)
        expect = [report['position']['accuracy'] for report in reports]
        gotten = [report['position']['accuracy'] for report in send_reports]
        self.assertEqual(set(expect), set(gotten))

        self.check_stats(
            counter=[('items.export.test.batches', 1, 1),
                     ('items.export.test.upload_status.200', 1)],
            timer=['items.export.test.upload'],
        )

    def test_upload_retried(self):
        self.add_reports(3)

        with requests_mock.Mocker() as mock:
            mock.register_uri('POST', requests_mock.ANY, [
                {'text': '', 'status_code': 500},
                {'text': '{}', 'status_code': 404},
                {'text': '{}', 'status_code': 200},
            ])
            # simulate celery retry handling
            for i in range(5):
                try:
                    schedule_export_reports.delay().get()
                except Retry:
                    continue
                else:
                    break
                self.fail('Task should have succeeded')

        self.assertEqual(mock.call_count, 3)
        self.check_stats(
            counter=[('items.export.test.batches', 1, 1),
                     ('items.export.test.upload_status.200', 1),
                     ('items.export.test.upload_status.404', 1),
                     ('items.export.test.upload_status.500', 1)],
            timer=[('items.export.test.upload', 3)],
        )


class TestS3Uploader(BaseTest, CeleryTestCase):

    def setUp(self):
        super(TestS3Uploader, self).setUp()
        config = DummyConfig({
            'export:backup': {
                'url': 's3://bucket/backups/{year}/{month}/{day}',
                'batch': '3',
            },
        })
        self.celery_app.export_queues = configure_export(config)

    def test_upload(self):
        reports = []
        reports.extend(self.add_reports(1, email='secretemail@localhost'))
        reports.extend(self.add_reports(1, api_key='e5444e9f-7946'))
        reports.extend(self.add_reports(1, api_key=None))

        with mock_s3() as mock_key:
            schedule_export_reports.delay().get()

        self.assertTrue(mock_key.set_contents_from_string.called)
        self.assertEqual(mock_key.content_encoding, 'gzip')
        self.assertEqual(mock_key.content_type, 'application/json')
        self.assertTrue(mock_key.key.startswith('backups/2'))
        self.assertTrue(mock_key.key.endswith('.json.gz'))
        self.assertTrue(mock_key.close.called)

        # check uploaded content
        args, kw = mock_key.set_contents_from_string.call_args
        uploaded_data = args[0]
        uploaded_text = util.decode_gzip(uploaded_data)

        # make sure we don't accidentally leak emails
        self.assertFalse('secretemail' in uploaded_text)

        send_reports = json.loads(uploaded_text)['items']
        self.assertEqual(len(send_reports), 3)
        expect = [report['position']['accuracy'] for report in reports]
        gotten = [report['position']['accuracy'] for report in send_reports]
        self.assertEqual(set(expect), set(gotten))

        self.check_stats(
            counter=[('items.export.backup.batches', 1, 1),
                     ('items.export.backup.upload_status.success', 1)],
            timer=['items.export.backup.upload'],
        )
