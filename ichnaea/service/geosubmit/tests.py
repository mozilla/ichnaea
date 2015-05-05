import time

from ichnaea.data.tasks import schedule_export_reports
from ichnaea.models import (
    Cell,
    CellObservation,
    Radio,
    User,
    Wifi,
    WifiObservation,
)
from ichnaea.tests.base import CeleryAppTestCase
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)
from ichnaea.util import utcnow


class TestGeoSubmit(CeleryAppTestCase):

    def _post(self, items, api_key='test', status=200, **kw):
        url = '/v1/geosubmit'
        if api_key:
            url += '?key=%s' % api_key
        res = self.app.post_json(url, {'items': items}, status=status, **kw)
        schedule_export_reports.delay().get()
        return res

    def test_ok_cell(self):
        cell = CellFactory()
        new_cell = CellFactory.build()
        self.session.flush()
        response = self._post([
            {'latitude': cell.lat,
             'longitude': cell.lon,
             'radioType': cell.radio.name,
             'cellTowers': [{
                 'mobileCountryCode': cell.mcc,
                 'mobileNetworkCode': cell.mnc,
                 'locationAreaCode': cell.lac,
                 'cellId': cell.cid,
             }]},
            {'latitude': new_cell.lat,
             'longitude': new_cell.lon,
             'cellTowers': [{
                 'radioType': new_cell.radio.name,
                 'mobileCountryCode': new_cell.mcc,
                 'mobileNetworkCode': new_cell.mnc,
                 'locationAreaCode': new_cell.lac,
                 'cellId': new_cell.cid,
             }]},
        ])
        # check that we get an empty response
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json, {})

        self.assertEqual(self.session.query(Cell).count(), 2)
        observations = self.session.query(CellObservation).all()
        self.assertEqual(len(observations), 2)
        radios = set([obs.radio for obs in observations])
        self.assertEqual(radios, set([cell.radio, new_cell.radio]))

        self.check_stats(
            counter=['geosubmit.api_key.test',
                     'items.api_log.test.uploaded.batches',
                     'items.api_log.test.uploaded.reports',
                     'items.api_log.test.uploaded.cell_observations',
                     'items.uploaded.cell_observations',
                     'items.uploaded.batches',
                     'items.uploaded.reports',
                     'request.v1.geosubmit.200',
                     ],
            timer=['items.api_log.test.uploaded.batch_size',
                   'items.uploaded.batch_size',
                   'request.v1.geosubmit'])

    def test_ok_no_existing_cell(self):
        now_ms = int(time.time() * 1000)
        first_of_month = utcnow().replace(day=1, hour=0, minute=0, second=0)
        cell = CellFactory.build()
        self._post([{
            'latitude': cell.lat,
            'longitude': cell.lon,
            'accuracy': 12.4,
            'altitude': 100.1,
            'altitudeAccuracy': 23.7,
            'heading': 45.0,
            'speed': 3.6,
            'timestamp': now_ms,
            'cellTowers': [{
                'radioType': cell.radio.name,
                'mobileCountryCode': cell.mcc,
                'mobileNetworkCode': cell.mnc,
                'locationAreaCode': cell.lac,
                'cellId': cell.cid,
                'age': 3,
                'asu': 31,
                'psc': cell.psc,
                'signalStrength': -51,
                'timingAdvance': 1,
            }],
        }])
        self.assertEquals(self.session.query(Cell).count(), 1)
        result = self.session.query(CellObservation).all()
        self.assertEquals(len(result), 1)
        obs = result[0]
        for name in ('lat', 'lon', 'radio', 'mcc', 'mnc', 'lac', 'cid', 'psc'):
            self.assertEqual(getattr(obs, name), getattr(cell, name))
        self.assertEqual(obs.accuracy, 12)
        self.assertEqual(obs.altitude, 100)
        self.assertEqual(obs.altitude_accuracy, 24)
        self.assertEqual(obs.heading, 45.0)
        self.assertEqual(obs.speed, 3.6)
        self.assertEqual(obs.time, first_of_month)
        self.assertEqual(obs.asu, 31)
        self.assertEqual(obs.signal, -51)
        self.assertEqual(obs.ta, 1)

    def test_ok_partial_cell(self):
        cell = CellFactory()
        self.session.flush()
        self._post([{
            'latitude': cell.lat,
            'longitude': cell.lon,
            'cellTowers': [{
                'radioType': cell.radio.name,
                'mobileCountryCode': cell.mcc,
                'mobileNetworkCode': cell.mnc,
                'locationAreaCode': cell.lac,
                'cellId': cell.cid,
                'psc': cell.psc}, {
                'radioType': cell.radio.name,
                'mobileCountryCode': cell.mcc,
                'mobileNetworkCode': cell.mnc,
                'psc': cell.psc + 1,
            }],
        }])
        observations = self.session.query(CellObservation).all()
        self.assertEqual(len(observations), 2)
        pscs = set([obs.psc for obs in observations])
        self.assertEqual(pscs, set([cell.psc, cell.psc + 1]))

    def test_ok_radioless_cell(self):
        cell = CellFactory.build()
        self._post([{
            'latitude': cell.lat,
            'longitude': cell.lon,
            'cellTowers': [{
                'mobileCountryCode': cell.mcc,
                'mobileNetworkCode': cell.mnc,
                'locationAreaCode': cell.lac,
                'cellId': cell.cid,
                'psc': cell.psc,
            }],
        }])
        observations = self.session.query(CellObservation).all()
        self.assertEqual(len(observations), 0)

    def test_ok_wifi(self):
        wifis = WifiFactory.create_batch(4)
        new_wifi = WifiFactory()
        self.session.flush()
        self._post([{
            'latitude': wifis[0].lat,
            'longitude': wifis[0].lon,
            'wifiAccessPoints': [
                {'macAddress': wifis[0].key},
                {'macAddress': wifis[1].key},
                {'macAddress': wifis[2].key},
                {'macAddress': wifis[3].key},
                {'macAddress': new_wifi.key},
            ]},
        ])
        query = self.session.query(Wifi)
        count = query.filter(Wifi.key == new_wifi.key).count()
        self.assertEquals(count, 1)
        self.assertEquals(self.session.query(WifiObservation).count(), 5)

        self.check_stats(
            counter=['items.api_log.test.uploaded.batches',
                     'items.api_log.test.uploaded.reports',
                     'items.api_log.test.uploaded.wifi_observations',
                     'items.uploaded.wifi_observations',
                     ],
            timer=['items.api_log.test.uploaded.batch_size'])

    def test_ok_no_existing_wifi(self):
        wifi = WifiFactory.build()
        self._post([{
            'latitude': wifi.lat,
            'longitude': wifi.lon,
            'wifiAccessPoints': [{
                'macAddress': wifi.key,
                'age': 3,
                'channel': 6,
                'frequency': 2437,
                'signalToNoiseRatio': 13,
                'signalStrength': -77,
            }],
        }])
        query = self.session.query(Wifi).filter(Wifi.key == wifi.key)
        self.assertEquals(query.count(), 1)

        result = self.session.query(WifiObservation).all()
        self.assertEquals(len(result), 1)
        obs = result[0]
        self.assertEqual(obs.lat, wifi.lat)
        self.assertEqual(obs.lon, wifi.lon)
        self.assertEqual(obs.key, wifi.key)
        self.assertEqual(obs.channel, 6)
        self.assertEqual(obs.signal, -77)
        self.assertEqual(obs.snr, 13)

    def test_invalid_float(self):
        wifi = WifiFactory.build()
        self._post([{
            'latitude': wifi.lat,
            'longitude': wifi.lon,
            'accuracy': float('+nan'),
            'altitude': float('-inf'),
            'wifiAccessPoints': [{
                'macAddress': wifi.key,
            }],
        }])
        obs = self.session.query(WifiObservation).all()
        self.assertEqual(len(obs), 1)
        self.assertFalse(obs[0].accuracy)
        self.assertFalse(obs[0].altitude)

    def test_invalid_json(self):
        wifi = WifiFactory.build()
        self._post([{
            'latitude': wifi.lat,
            'longitude': wifi.lon,
            'wifiAccessPoints': [{
                'macAddress': 10,
            }],
        }], status=400)
        self.assertEquals(self.session.query(WifiObservation).count(), 0)

    def test_invalid_latitude(self):
        wifi = WifiFactory.build()
        self._post([{
            'latitude': 12345.0,
            'longitude': wifi.lon,
            'wifiAccessPoints': [{
                'macAddress': wifi.key,
            }],
        }])
        self.assertEquals(self.session.query(WifiObservation).count(), 0)

    def test_invalid_cell(self):
        cell = CellFactory.build()
        self._post([{
            'latitude': cell.lat,
            'longitude': cell.lon,
            'cellTowers': [{
                'radioType': cell.radio.name,
                'mobileCountryCode': cell.mcc,
                'mobileNetworkCode': 2000,
                'locationAreaCode': cell.lac,
                'cellId': cell.cid,
            }],
        }])
        self.assertEquals(self.session.query(CellObservation).count(), 0)

    def test_invalid_radiotype(self):
        cell = CellFactory.build()
        cell2 = CellFactory.build(radio=Radio.wcdma)
        self._post([{
            'latitude': cell.lat,
            'longitude': cell.lon,
            'cellTowers': [{
                'radioType': '18',
                'mobileCountryCode': cell.mcc,
                'mobileNetworkCode': cell.mnc,
                'locationAreaCode': cell.lac,
                'cellId': cell.cid,
            }, {
                'radioType': 'umts',
                'mobileCountryCode': cell2.mcc,
                'mobileNetworkCode': cell2.mnc,
                'locationAreaCode': cell2.lac,
                'cellId': cell2.cid,
            }],
        }])
        obs = self.session.query(CellObservation).all()
        self.assertEqual(len(obs), 1)
        self.assertEqual(obs[0].cid, cell2.cid)

    def test_duplicated_cell_observations(self):
        cell = CellFactory.build()
        self._post([{
            'latitude': cell.lat,
            'longitude': cell.lon,
            'cellTowers': [
                {'radioType': cell.radio.name,
                 'mobileCountryCode': cell.mcc,
                 'mobileNetworkCode': cell.mnc,
                 'locationAreaCode': cell.lac,
                 'cellId': cell.cid,
                 'asu': 10},
                {'radioType': cell.radio.name,
                 'mobileCountryCode': cell.mcc,
                 'mobileNetworkCode': cell.mnc,
                 'locationAreaCode': cell.lac,
                 'cellId': cell.cid,
                 'asu': 16},
            ],
        }])
        self.assertEquals(self.session.query(CellObservation).count(), 1)

    def test_duplicated_wifi_observations(self):
        wifi = WifiFactory.build()
        self._post([{
            'latitude': wifi.lat,
            'longitude': wifi.lon,
            'wifiAccessPoints': [
                {'macAddress': wifi.key,
                 'signalStrength': -92},
                {'macAddress': wifi.key,
                 'signalStrength': -77},
            ],
        }])
        self.assertEquals(self.session.query(WifiObservation).count(), 1)

    def test_email_header(self):
        nickname = 'World Tr\xc3\xa4veler'
        email = 'world_tr\xc3\xa4veler@email.com'
        wifis = WifiFactory.create_batch(2)
        self._post([{
            'latitude': wifis[0].lat,
            'longitude': wifis[0].lon,
            'wifiAccessPoints': [
                {'macAddress': wifis[0].key},
                {'macAddress': wifis[1].key},
            ],
        }], headers={'X-Nickname': nickname, 'X-Email': email})

        result = self.session.query(User).all()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].email, email.decode('utf-8'))

    def test_batches(self):
        batch = 110
        wifis = WifiFactory.create_batch(batch)
        items = [{'latitude': wifi.lat,
                  'longitude': wifi.lon,
                  'wifiAccessPoints': [{'macAddress': wifi.key}]}
                 for wifi in wifis]

        # let's add a bad one, this will just be skipped
        items.append({'lat': 10.0, 'lon': 10.0, 'whatever': 'xx'})
        self._post(items)

        self.assertEqual(self.session.query(WifiObservation).count(), batch)

    def test_log_unknown_api_key(self):
        wifis = WifiFactory.create_batch(2)
        self._post([{
            'latitude': wifis[0].lat,
            'longitude': wifis[0].lon,
            'wifiAccessPoints': [
                {'macAddress': wifis[0].key},
                {'macAddress': wifis[1].key},
            ],
        }], api_key='invalidkey')

        self.check_stats(
            counter=['geosubmit.unknown_api_key',
                     ('geosubmit.api_key.invalidkey', 0)])
