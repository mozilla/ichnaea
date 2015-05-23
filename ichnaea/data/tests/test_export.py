from contextlib import contextmanager
import json
import time

import boto
import mock
import requests_mock

from ichnaea.async.config import configure_export
from ichnaea.config import DummyConfig
from ichnaea.data.tasks import (
    location_update_cell,
    location_update_wifi,
    schedule_export_reports,
    queue_reports,
)
from ichnaea.models import (
    ApiKey,
    Cell,
    Wifi,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)
from ichnaea import util


@contextmanager
def mock_s3(mock_keys):
    mock_conn = mock.MagicMock()

    def new_mock(*args, **kw):
        mock_key = mock.MagicMock()
        mock_key(*args, **kw)
        mock_keys.append(mock_key)
        return mock_key

    with mock.patch.object(boto, 'connect_s3', mock_conn):
        with mock.patch('boto.s3.key.Key', new_mock) as mock_key:
            yield mock_key


class BaseExportTest(CeleryTestCase):

    def add_reports(self, number, cell_factor=1, wifi_factor=2,
                    api_key='test', email=None, ip=None):
        reports = []
        for i in range(number):
            pos = CellFactory.build()
            report = {
                'timestamp': time.time() * 1000.0,
                'position': {},
                'cellTowers': [],
                'wifiAccessPoints': [],
            }
            report['position']['latitude'] = pos.lat
            report['position']['longitude'] = pos.lon
            report['position']['accuracy'] = 17 + i

            cells = CellFactory.build_batch(cell_factor,
                                            lat=pos.lat, lon=pos.lon)
            for cell in cells:
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

            wifis = WifiFactory.build_batch(wifi_factor,
                                            lat=pos.lat, lon=pos.lon)
            for wifi in wifis:
                wifi_data = {
                    'macAddress': wifi.key,
                    'signalStrength': -90 + i,
                }
                report['wifiAccessPoints'].append(wifi_data)

            reports.append(report)

        queue_reports.delay(
            reports=reports, api_key=api_key, email=email, ip=ip).get()
        return reports

    def queue_length(self, redis_key):
        return self.redis_client.llen(redis_key)


class TestExporter(BaseExportTest):

    def setUp(self):
        super(TestExporter, self).setUp()
        config = DummyConfig({
            'export:test': {
                'url': None,
                'skip_keys': 'export_source',
                'batch': '3',
            },
            'export:everything': {
                'url': '',
                'batch': '5',
            },
            'export:no_test': {
                'skip_keys': 'test_1 test\ntest:-1',
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
        self.celery_app.export_queues = queues = configure_export(
            self.redis_client, config)
        self.test_queue_key = queues['test'].queue_key()
        self.session.add(ApiKey(valid_key='test2', log=True))
        self.session.flush()

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


class TestGeosubmitUploader(BaseExportTest):

    def setUp(self):
        super(TestGeosubmitUploader, self).setUp()
        config = DummyConfig({
            'export:test': {
                'url': 'http://127.0.0.1:9/v2/geosubmit?key=external',
                'batch': '3',
            },
        })
        self.celery_app.export_queues = configure_export(
            self.redis_client, config)

    def test_upload(self):
        self.session.add(ApiKey(valid_key='e5444-794', log=True))
        self.session.flush()

        reports = []
        reports.extend(self.add_reports(1, email='secretemail@localhost',
                                        ip=self.geoip_data['London']['ip']))
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
        # make sure we don't accidentally leak emails or IPs
        self.assertFalse('secretemail' in body)
        self.assertFalse(self.geoip_data['London']['ip'] in body)

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


class TestInternalUploader(BaseExportTest):

    def setUp(self):
        super(TestInternalUploader, self).setUp()
        config = DummyConfig({
            'export:internal': {
                'url': 'internal://',
                'metadata': 'true',
                'batch': '0',
            },
        })
        self.celery_app.export_queues = configure_export(
            self.redis_client, config)

    def test_upload(self):
        self.session.add(ApiKey(valid_key='e5444-794', log=True))
        self.session.flush()

        self.add_reports(3, email='secretemail@localhost',
                         ip=self.geoip_data['London']['ip'])
        self.add_reports(6, api_key='e5444-794')
        self.add_reports(3, api_key=None)

        schedule_export_reports.delay().get()
        location_update_cell.delay().get()
        location_update_wifi.delay().get()

        self.assertEqual(self.session.query(Cell).count(), 12)
        self.assertEqual(self.session.query(Wifi).count(), 24)

        self.check_stats(counter=[
            ('items.export.internal.batches', 1, 1),
            ('items.api_log.test.uploaded.cell_observations', 1, 3),
            ('items.api_log.test.uploaded.wifi_observations', 1, 6),
            ('items.api_log.no_key.uploaded.cell_observations', 0),
            ('items.api_log.e5444-794.uploaded.cell_observations', 1, 6),
            ('items.api_log.e5444-794.uploaded.wifi_observations', 1, 12),
        ])

    def test_upload_cell(self):
        reports = self.add_reports(1, cell_factor=1, wifi_factor=0)
        schedule_export_reports.delay().get()
        location_update_cell.delay().get()

        position = reports[0]['position']
        cell_data = reports[0]['cellTowers'][0]

        cells = self.session.query(Cell).all()
        self.assertEqual(len(cells), 1)
        cell = cells[0]

        self.assertEqual(cell.lat, position['latitude'])
        self.assertEqual(cell.lon, position['longitude'])
        self.assertEqual(cell.radio.name, cell_data['radioType'])
        self.assertEqual(cell.mcc, cell_data['mobileCountryCode'])
        self.assertEqual(cell.mnc, cell_data['mobileNetworkCode'])
        self.assertEqual(cell.lac, cell_data['locationAreaCode'])
        self.assertEqual(cell.cid, cell_data['cellId'])
        self.assertEqual(cell.psc, cell_data['primaryScramblingCode'])
        self.assertEqual(cell.total_measures, 1)

    def test_upload_wifi(self):
        reports = self.add_reports(1, cell_factor=0, wifi_factor=1)
        schedule_export_reports.delay().get()
        location_update_wifi.delay().get()

        position = reports[0]['position']
        wifi_data = reports[0]['wifiAccessPoints'][0]

        wifis = self.session.query(Wifi).all()
        self.assertEqual(len(wifis), 1)
        wifi = wifis[0]

        self.assertEqual(wifi.lat, position['latitude'])
        self.assertEqual(wifi.lon, position['longitude'])
        self.assertEqual(wifi.key, wifi_data['macAddress'])
        self.assertEqual(wifi.total_measures, 1)


class TestS3Uploader(BaseExportTest):

    def setUp(self):
        super(TestS3Uploader, self).setUp()
        config = DummyConfig({
            'export:backup': {
                'url': 's3://bucket/backups/{api_key}/{year}/{month}/{day}',
                'batch': '3',
            },
        })
        self.celery_app.export_queues = configure_export(
            self.redis_client, config)

    def test_no_monitoring(self):
        export_queue = self.celery_app.export_queues['backup']
        self.assertFalse(export_queue.monitor_name)

    def test_upload(self):
        self.session.add(ApiKey(valid_key='e5444-794', log=True))
        self.session.flush()

        reports = self.add_reports(3, email='secretemail@localhost',
                                   ip=self.geoip_data['London']['ip'])
        self.add_reports(6, api_key='e5444-794')
        self.add_reports(3, api_key=None)

        mock_keys = []
        with mock_s3(mock_keys):
            schedule_export_reports.delay().get()

        self.assertEqual(len(mock_keys), 4)

        keys = []
        test_export = None
        for mock_key in mock_keys:
            self.assertTrue(mock_key.set_contents_from_string.called)
            self.assertEqual(mock_key.content_encoding, 'gzip')
            self.assertEqual(mock_key.content_type, 'application/json')
            self.assertTrue(mock_key.key.startswith('backups/'))
            self.assertTrue(mock_key.key.endswith('.json.gz'))
            self.assertTrue(mock_key.close.called)
            keys.append(mock_key.key)
            if 'test' in mock_key.key:
                test_export = mock_key

        # extract second path segment from key names
        queue_keys = [key.split('/')[1] for key in keys]
        self.assertEqual(set(queue_keys), set(['test', 'no_key', 'e5444-794']))

        # check uploaded content
        args, kw = test_export.set_contents_from_string.call_args
        uploaded_data = args[0]
        uploaded_text = util.decode_gzip(uploaded_data)

        # make sure we don't accidentally leak emails or IPs
        self.assertFalse('secretemail' in uploaded_text)
        self.assertFalse(self.geoip_data['London']['ip'] in uploaded_text)

        send_reports = json.loads(uploaded_text)['items']
        self.assertEqual(len(send_reports), 3)
        expect = [report['position']['accuracy'] for report in reports]
        gotten = [report['position']['accuracy'] for report in send_reports]
        self.assertEqual(set(expect), set(gotten))

        self.check_stats(
            counter=[('items.export.backup.batches', 4, 1),
                     ('items.export.backup.upload_status.success', 4)],
            timer=[('items.export.backup.upload', 4)],
        )
