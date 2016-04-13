from contextlib import contextmanager
import time

import boto
import mock
import requests_mock
import simplejson

from ichnaea.data.export import DummyExporter
from ichnaea.data.tasks import (
    update_blue,
    update_cell,
    update_incoming,
    update_wifi,
)
from ichnaea.models import (
    BlueShard,
    CellShard,
    WifiShard,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    ApiKeyFactory,
    BlueShardFactory,
    CellShardFactory,
    ExportConfigFactory,
    WifiShardFactory,
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

    def setUp(self):
        super(BaseExportTest, self).setUp()
        self.queue = self.celery_app.data_queues['update_incoming']
        self.timestamp = int(time.time() * 1000)

    def add_reports(self, num=1, blue_factor=0, cell_factor=1, wifi_factor=2,
                    blue_key=None, cell_mcc=None, wifi_key=None,
                    api_key='test', lat=None, lon=None, source=None):
        reports = []
        for i in range(num):
            pos = CellShardFactory.build()
            report = {
                'timestamp': self.timestamp,
                'position': {},
                'bluetoothBeacons': [],
                'cellTowers': [],
                'wifiAccessPoints': [],
            }
            report['position']['latitude'] = lat or pos.lat
            report['position']['longitude'] = lon or pos.lon
            report['position']['accuracy'] = 17.0 + i
            if source is not None:
                report['position']['source'] = source

            blues = BlueShardFactory.build_batch(blue_factor,
                                                 lat=pos.lat, lon=pos.lon)
            for blue in blues:
                blue_data = {
                    'macAddress': blue_key or blue.mac,
                    'signalStrength': -100 + i,
                }
                report['bluetoothBeacons'].append(blue_data)

            cells = CellShardFactory.build_batch(cell_factor,
                                                 lat=pos.lat, lon=pos.lon)
            for cell in cells:
                cell_data = {
                    'radioType': cell.radio.name,
                    'mobileCountryCode': cell_mcc or cell.mcc,
                    'mobileNetworkCode': cell.mnc,
                    'locationAreaCode': cell.lac,
                    'cellId': cell.cid,
                    'primaryScramblingCode': cell.psc,
                    'signalStrength': -110 + i,
                }
                report['cellTowers'].append(cell_data)

            wifis = WifiShardFactory.build_batch(wifi_factor,
                                                 lat=pos.lat, lon=pos.lon)
            for wifi in wifis:
                wifi_data = {
                    'macAddress': wifi_key or wifi.mac,
                    'signalStrength': -90 + i,
                    'ssid': 'my-wifi',
                }
                report['wifiAccessPoints'].append(wifi_data)

            reports.append(report)

        items = [{'api_key': api_key, 'report': rep} for rep in reports]

        self.queue.enqueue(items)
        return reports

    def queue_length(self, redis_key):
        return self.redis_client.llen(redis_key)


class TestExporter(BaseExportTest):

    def setUp(self):
        super(TestExporter, self).setUp()
        ApiKeyFactory(valid_key='test2')
        ExportConfigFactory(name='test', batch=3,
                            skip_keys=frozenset(['export_source']))
        ExportConfigFactory(name='everything', batch=5)
        ExportConfigFactory(name='no_test', batch=2,
                            skip_keys=frozenset(['test', 'test_1']))

        self.session.flush()

    def test_queues(self):
        self.add_reports(4)
        self.add_reports(1, api_key='test2')
        self.add_reports(2, api_key=None)
        update_incoming.delay().get()

        for queue_key, num in [
                ('queue_export_test', 1),
                ('queue_export_everything', 2),
                ('queue_export_no_test', 1)]:
            self.assertEqual(self.queue_length(queue_key), num)

    def test_retry(self):
        self.add_reports(3)

        num = [0]
        orig_wait = DummyExporter._retry_wait

        def mock_send(self, data, num=num):
            num[0] += 1
            if num[0] == 1:
                raise IOError()

        with mock.patch('ichnaea.data.export.DummyExporter.send', mock_send):
            try:
                DummyExporter._retry_wait = 0.001
                update_incoming.delay().get()
            finally:
                DummyExporter._retry_wait = orig_wait

        self.assertEqual(self.queue_length('queue_export_test'), 0)


class TestGeosubmit(BaseExportTest):

    def setUp(self):
        super(TestGeosubmit, self).setUp()
        ExportConfigFactory(
            name='test', batch=3, schema='geosubmit',
            url='http://127.0.0.1:9/v2/geosubmit?key=external')
        self.session.flush()

    def test_upload(self):
        ApiKeyFactory(valid_key='e5444-794')
        self.session.flush()

        reports = []
        reports.extend(self.add_reports(1, source='gnss'))
        reports.extend(self.add_reports(1, api_key='e5444e9f-7946'))
        reports.extend(self.add_reports(1, api_key=None))

        with requests_mock.Mocker() as mock:
            mock.register_uri('POST', requests_mock.ANY, text='{}')
            update_incoming.delay().get()

        self.assertEqual(mock.call_count, 1)
        req = mock.request_history[0]

        # check headers
        self.assertEqual(req.headers['Content-Type'], 'application/json')
        self.assertEqual(req.headers['Content-Encoding'], 'gzip')
        self.assertEqual(req.headers['User-Agent'], 'ichnaea')

        body = util.decode_gzip(req.body)
        send_reports = simplejson.loads(body)['items']
        self.assertEqual(len(send_reports), 3)

        for field in ('accuracy', 'source', 'timestamp'):
            expect = [report['position'].get(field) for report in reports]
            gotten = [report['position'].get(field) for report in send_reports]
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


class TestS3(BaseExportTest):

    def setUp(self):
        super(TestS3, self).setUp()
        ExportConfigFactory(
            name='backup', batch=3, schema='s3',
            url='s3://bucket/backups/{api_key}/{year}/{month}/{day}')
        self.session.flush()

    def test_upload(self):
        ApiKeyFactory(valid_key='e5444-794')
        self.session.flush()

        reports = self.add_reports(3)
        self.add_reports(3, api_key='e5444-794', source='gnss')
        self.add_reports(3, api_key='e5444-794', source='fused')
        self.add_reports(3, api_key=None)

        mock_keys = []
        with mock_s3(mock_keys):
            update_incoming.delay().get()

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

        send_reports = simplejson.loads(uploaded_text)['items']
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


class TestInternal(BaseExportTest):

    def setUp(self):
        super(TestInternal, self).setUp()
        ExportConfigFactory(name='internal', batch=0, schema='internal')
        self.session.flush()

    def _pop_item(self):
        return self.queue.dequeue()[0]

    def _push_item(self, item):
        self.queue.enqueue([item])

    def _update_all(self):
        update_incoming.delay().get()

        for shard_id in BlueShard.shards().keys():
            update_blue.delay(shard_id=shard_id).get()

        for shard_id in CellShard.shards().keys():
            update_cell.delay(shard_id=shard_id).get()

        for shard_id in WifiShard.shards().keys():
            update_wifi.delay(shard_id=shard_id).get()

    def test_stats(self):
        ApiKeyFactory(valid_key='e5444-794')
        self.session.flush()

        self.add_reports(3)
        self.add_reports(3, api_key='e5444-794', source='gnss')
        self.add_reports(3, api_key='e5444-794', source='query')
        self.add_reports(3, api_key=None)
        self._update_all()

        self.check_stats(counter=[
            ('data.export.batch', 1, 1, ['key:internal']),
            ('data.report.upload', 2, 3),
            ('data.report.upload', 1, 3, ['key:test']),
            ('data.report.upload', 1, 6, ['key:e5444-794']),
            ('data.observation.upload', 1, 3, ['type:cell', 'key:test']),
            ('data.observation.upload', 1, 6, ['type:wifi', 'key:test']),
            ('data.observation.upload', 0, ['type:cell', 'key:no_key']),
            ('data.observation.upload', 1, 6, ['type:cell', 'key:e5444-794']),
            ('data.observation.upload', 1, 12, ['type:wifi', 'key:e5444-794']),
        ])
        # we get a variable number of statsd messages and are only
        # interested in the sum-total
        for name, total in (('cell', 12), ('wifi', 24)):
            insert_msgs = [msg for msg in self.stats_client.msgs
                           if (msg.startswith('data.observation.insert') and
                               'type:' + name in msg)]
            self.assertEqual(sum([int(msg.split(':')[1].split('|')[0])
                                  for msg in insert_msgs]),
                             total)

    def test_blue(self):
        reports = self.add_reports(blue_factor=1, cell_factor=0, wifi_factor=0)
        self._update_all()

        position = reports[0]['position']
        wifi_data = reports[0]['bluetoothBeacons'][0]
        mac = wifi_data['macAddress']
        shard = BlueShard.shard_model(mac)
        blues = self.session.query(shard).all()
        self.assertEqual(len(blues), 1)
        blue = blues[0]
        self.assertEqual(blue.lat, position['latitude'])
        self.assertEqual(blue.lon, position['longitude'])
        self.assertEqual(blue.mac, wifi_data['macAddress'])
        self.assertEqual(blue.samples, 1)

    def test_blue_duplicated(self):
        self.add_reports(blue_factor=1, cell_factor=0, wifi_factor=0)
        # duplicate the Bluetooth entry inside the report
        item = self._pop_item()
        report = item['report']
        blue = report['bluetoothBeacons'][0]
        mac = blue['macAddress']
        report['bluetoothBeacons'].append(blue.copy())
        report['bluetoothBeacons'].append(blue.copy())
        report['bluetoothBeacons'][1]['signalStrength'] += 2
        report['bluetoothBeacons'][2]['signalStrength'] -= 2
        self._push_item(item)
        self._update_all()

        shard = BlueShard.shard_model(mac)
        blues = self.session.query(shard).all()
        self.assertEqual(len(blues), 1)
        self.assertEqual(blues[0].samples, 1)

    def test_bluetooth_invalid(self):
        self.add_reports(blue_factor=1, cell_factor=0, wifi_factor=0,
                         blue_key='abcd')
        self._update_all()

    def test_cell(self):
        reports = self.add_reports(cell_factor=1, wifi_factor=0)
        self._update_all()

        position = reports[0]['position']
        cell_data = reports[0]['cellTowers'][0]
        radio = cell_data['radioType']
        shard = CellShard.shard_model(radio)
        cells = self.session.query(shard).all()
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
        self.assertEqual(cell.samples, 1)

    def test_cell_duplicated(self):
        self.add_reports(cell_factor=1, wifi_factor=0)
        # duplicate the cell entry inside the report
        item = self._pop_item()
        report = item['report']
        cell = report['cellTowers'][0]
        radio = cell['radioType']
        report['cellTowers'].append(cell.copy())
        report['cellTowers'].append(cell.copy())
        report['cellTowers'][1]['signalStrength'] += 2
        report['cellTowers'][2]['signalStrength'] -= 2
        self._push_item(item)
        self._update_all()

        shard = CellShard.shard_model(radio)
        cells = self.session.query(shard).all()
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0].samples, 1)

    def test_cell_invalid(self):
        self.add_reports(cell_factor=1, wifi_factor=0, cell_mcc=-2)
        self._update_all()

        self.check_stats(counter=[
            ('data.report.upload', 1, 1, ['key:test']),
            ('data.report.drop', 1, 1, ['key:test']),
            ('data.observation.drop', 1, 1, ['type:cell', 'key:test']),
        ])

    def test_wifi(self):
        reports = self.add_reports(cell_factor=0, wifi_factor=1)
        self._update_all()

        position = reports[0]['position']
        wifi_data = reports[0]['wifiAccessPoints'][0]
        mac = wifi_data['macAddress']
        shard = WifiShard.shard_model(mac)
        wifis = self.session.query(shard).all()
        self.assertEqual(len(wifis), 1)
        wifi = wifis[0]
        self.assertEqual(wifi.lat, position['latitude'])
        self.assertEqual(wifi.lon, position['longitude'])
        self.assertEqual(wifi.mac, wifi_data['macAddress'])
        self.assertEqual(wifi.samples, 1)

    def test_wifi_duplicated(self):
        self.add_reports(cell_factor=0, wifi_factor=1)
        # duplicate the wifi entry inside the report
        item = self._pop_item()
        report = item['report']
        wifi = report['wifiAccessPoints'][0]
        mac = wifi['macAddress']
        report['wifiAccessPoints'].append(wifi.copy())
        report['wifiAccessPoints'].append(wifi.copy())
        report['wifiAccessPoints'][1]['signalStrength'] += 2
        report['wifiAccessPoints'][2]['signalStrength'] -= 2
        self._push_item(item)
        self._update_all()

        shard = WifiShard.shard_model(mac)
        wifis = self.session.query(shard).all()
        self.assertEqual(len(wifis), 1)
        self.assertEqual(wifis[0].samples, 1)

    def test_wifi_invalid(self):
        self.add_reports(cell_factor=0, wifi_factor=1, wifi_key='abcd')
        self._update_all()

        self.check_stats(counter=[
            ('data.report.upload', 1, 1, ['key:test']),
            ('data.report.drop', 1, 1, ['key:test']),
            ('data.observation.drop', 1, 1, ['type:wifi', 'key:test']),
        ])

    def test_position_invalid(self):
        self.add_reports(1, cell_factor=0, wifi_factor=1,
                         wifi_key='000000123456', lat=-90.1)
        self.add_reports(1, cell_factor=0, wifi_factor=1,
                         wifi_key='000000234567')
        self._update_all()

        shard = WifiShard.shards()['0']
        self.assertEqual(self.session.query(shard).count(), 1)
        self.check_stats(counter=[
            ('data.report.upload', 1, 2, ['key:test']),
            ('data.report.drop', 1, 1, ['key:test']),
            ('data.observation.insert', 1, 1, ['type:wifi']),
            ('data.observation.upload', 1, 1, ['type:wifi', 'key:test']),
        ])

    def test_no_observations(self):
        self.add_reports(1, cell_factor=0, wifi_factor=0)
        self._update_all()

    def test_datamap(self):
        self.add_reports(1, cell_factor=0, wifi_factor=2, lat=50.0, lon=10.0)
        self.add_reports(2, cell_factor=0, wifi_factor=2, lat=20.0, lon=-10.0)
        update_incoming.delay().get()
        self.assertEqual(
            self.celery_app.data_queues['update_datamap_ne'].size(), 1)
        self.assertEqual(
            self.celery_app.data_queues['update_datamap_sw'].size(), 1)
