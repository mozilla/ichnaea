import time

from ichnaea.data.tasks import (
    update_incoming,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    BlueShardFactory,
    CellShardFactory,
    WifiShardFactory,
)


class BaseExportTest(CeleryTestCase):

    def setUp(self):
        super(BaseExportTest, self).setUp()
        self.incoming_queue = self.celery_app.data_queues['update_incoming']

    def add_reports(self, num=1, blue_factor=0, cell_factor=1, wifi_factor=2,
                    api_key='test', nickname=None,
                    blue_key=None, cell_mcc=None, wifi_key=None,
                    lat=None, lon=None):
        reports = []
        for i in range(num):
            pos = CellShardFactory.build()
            report = {
                'timestamp': time.time() * 1000.0,
                'position': {},
                'bluetoothBeacons': [],
                'cellTowers': [],
                'wifiAccessPoints': [],
            }
            report['position']['latitude'] = lat or pos.lat
            report['position']['longitude'] = lon or pos.lon
            report['position']['accuracy'] = 17.0 + i

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

        items = [{'api_key': api_key,
                  'nickname': nickname,
                  'report': rep} for rep in reports]

        self.incoming_queue.enqueue(items)
        update_incoming.delay().get()
        return reports

    def queue_length(self, redis_key):
        return self.redis_client.llen(redis_key)
