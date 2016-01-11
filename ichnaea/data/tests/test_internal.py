from ichnaea.async.config import configure_export
from ichnaea.config import DummyConfig
from ichnaea.data.tasks import (
    update_cell,
    update_wifi,
    schedule_export_reports,
)
from ichnaea.data.tests.test_export import BaseExportTest
from ichnaea.models import (
    CellShard,
    ScoreKey,
    User,
    WifiShard,
)
from ichnaea.tests.factories import ApiKeyFactory


class TestUploader(BaseExportTest):

    nickname = b'World Tr\xc3\xa4veler'.decode('utf-8')

    def setUp(self):
        super(TestUploader, self).setUp()
        config = DummyConfig({
            'export:internal': {
                'url': 'internal://',
                'metadata': 'true',
                'batch': '0',
            },
        })
        self.celery_app.export_queues = configure_export(
            self.redis_client, config)

    def _update_all(self):
        schedule_export_reports.delay().get()

        for shard_id in CellShard.shards().keys():
            update_cell.delay(shard_id=shard_id).get()

        for shard_id in WifiShard.shards().keys():
            update_wifi.delay(shard_id=shard_id).get()

    def test_stats(self):
        ApiKeyFactory(valid_key='e5444-794', log_submit=True)
        self.session.flush()

        self.add_reports(3, ip=self.geoip_data['London']['ip'])
        self.add_reports(6, api_key='e5444-794')
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
        queue = self.celery_app.export_queues['internal']
        items = queue.dequeue(queue.queue_key())
        report = items[0]['report']
        cell = report['cellTowers'][0]
        radio = cell['radioType']
        report['cellTowers'].append(cell.copy())
        report['cellTowers'].append(cell.copy())
        report['cellTowers'][1]['signalStrength'] += 2
        report['cellTowers'][2]['signalStrength'] -= 2
        queue.enqueue(items, queue.queue_key())
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
            ('data.report.drop', 1, 1, ['reason:malformed', 'key:test']),
            ('data.observation.drop', 1, 1,
                ['type:cell', 'reason:malformed', 'key:test']),
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
        queue = self.celery_app.export_queues['internal']
        items = queue.dequeue(queue.queue_key())
        report = items[0]['report']
        wifi = report['wifiAccessPoints'][0]
        mac = wifi['macAddress']
        report['wifiAccessPoints'].append(wifi.copy())
        report['wifiAccessPoints'].append(wifi.copy())
        report['wifiAccessPoints'][1]['signalStrength'] += 2
        report['wifiAccessPoints'][2]['signalStrength'] -= 2
        queue.enqueue(items, queue.queue_key())
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
            ('data.report.drop', 1, 1, ['reason:malformed', 'key:test']),
            ('data.observation.drop', 1, 1,
                ['type:wifi', 'reason:malformed', 'key:test']),
        ])

    def test_bluetooth(self):
        self.add_reports(blue_factor=1, cell_factor=0, wifi_factor=0)
        schedule_export_reports.delay().get()

    def test_bluetooth_invalid(self):
        self.add_reports(blue_factor=1, cell_factor=0, wifi_factor=0,
                         blue_key='abcd')
        schedule_export_reports.delay().get()

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
            ('data.report.drop', 1, 1, ['reason:malformed', 'key:test']),
            ('data.observation.insert', 1, 1, ['type:wifi']),
            ('data.observation.upload', 1, 1, ['type:wifi', 'key:test']),
        ])

    def test_datamap(self):
        self.add_reports(1, cell_factor=0, wifi_factor=2, lat=50.0, lon=10.0)
        self.add_reports(2, cell_factor=0, wifi_factor=2, lat=20.0, lon=-10.0)
        schedule_export_reports.delay().get()
        self.assertEqual(
            self.celery_app.data_queues['update_datamap_ne'].size(), 1)
        self.assertEqual(
            self.celery_app.data_queues['update_datamap_sw'].size(), 1)

    def test_nickname(self):
        self.add_reports(wifi_factor=0, nickname=self.nickname)
        schedule_export_reports.delay().get()

        queue = self.celery_app.data_queues['update_score']
        self.assertEqual(queue.size(), 2)
        scores = queue.dequeue()
        score_keys = set([score['hashkey'].key for score in scores])
        self.assertEqual(
            score_keys, set([ScoreKey.location, ScoreKey.new_cell]))

        users = self.session.query(User).all()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].nickname, self.nickname)

    def test_nickname_too_short(self):
        self.add_reports(nickname=u'a')
        schedule_export_reports.delay().get()

        queue = self.celery_app.data_queues['update_score']
        self.assertEqual(queue.size(), 0)
        self.assertEqual(self.session.query(User).count(), 0)
