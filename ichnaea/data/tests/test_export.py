import time

from requests.exceptions import ConnectionError
from simplejson import dumps

from ichnaea.data.export import (
    check_queue_length,
    enqueue_reports,
)
from ichnaea.data.tasks import (
    export_reports,
    upload_reports,
    queue_reports,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)


class BaseTest(object):

    def add_reports(self, number=3):
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

        queue_reports.delay(reports=reports, api_key='test').get()
        return reports

    def check_queue_length(self):
        return check_queue_length(self.redis_client)


class TestExporter(BaseTest, CeleryTestCase):

    def test_enqueue_reports(self):
        reports = self.add_reports(2)
        enqueue_reports(self.redis_client, reports)
        self.assertEqual(self.check_queue_length(), 4)

    def test_too_little_data(self):
        self.add_reports(2)
        length = export_reports.delay(batch=10).get()
        # nothing was processed, all reports still in queue
        self.assertEqual(length, 0)
        self.assertEqual(self.check_queue_length(), 2)

    def test_one_batch(self):
        self.add_reports(6)
        length = export_reports.delay(batch=5).get()
        self.assertEqual(length, 5)
        self.assertEqual(self.check_queue_length(), 1)

    def test_multiple_batches(self):
        self.add_reports(11)
        length = export_reports.delay(batch=3).get()
        self.assertEqual(length, 3)
        self.assertEqual(self.check_queue_length(), 2)


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
