from contextlib import contextmanager

import boto
import mock
import requests_mock
import simplejson as json

from ichnaea.async.config import configure_export
from ichnaea.config import DummyConfig
from ichnaea.data.tasks import (
    schedule_export_reports,
)
from ichnaea.data.tests.base import BaseExportTest
from ichnaea.tests.factories import (
    ApiKeyFactory,
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
        ApiKeyFactory(valid_key='e5444-794', log_submit=True)
        self.session.flush()

        reports = []
        reports.extend(self.add_reports(1))
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

        # make sure a standards based json can decode this data
        # and none of our internal_json structures end up in it
        body = util.decode_gzip(req.body)
        send_reports = json.loads(body)['items']
        self.assertEqual(len(send_reports), 3)
        expect = [report['position']['accuracy'] for report in reports]
        gotten = [report['position']['accuracy'] for report in send_reports]
        self.assertEqual(set(expect), set(gotten))

        self.assertEqual(
            set([w['ssid'] for w in send_reports[0]['wifiAccessPoints']]),
            set(['my-wifi']))

        self.check_stats(counter=[
            ('data.export.batch', 1, 1, ['key:test']),
            ('data.export.upload', 1, ['key:test', 'status:200']),
        ], timer=[
            ('data.export.upload', ['key:test']),
        ])


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
        ApiKeyFactory(valid_key='e5444-794', log_submit=True)
        self.session.flush()

        reports = self.add_reports(3)
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

        send_reports = json.loads(uploaded_text)['items']
        self.assertEqual(len(send_reports), 3)
        expect = [report['position']['accuracy'] for report in reports]
        gotten = [report['position']['accuracy'] for report in send_reports]
        self.assertEqual(set(expect), set(gotten))

        self.check_stats(counter=[
            ('data.export.batch', 4, 1, ['key:backup']),
            ('data.export.upload', 4, ['key:backup', 'status:success']),
        ], timer=[
            ('data.export.upload', 4, ['key:backup']),
        ])
