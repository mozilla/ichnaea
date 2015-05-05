import uuid

from pyramid.testing import DummyRequest

from ichnaea.models.content import (
    Score,
    ScoreKey,
    User,
)
from ichnaea.models import (
    CellObservation,
    Radio,
    WifiObservation,
)
from ichnaea.customjson import dumps
from ichnaea.data.tasks import schedule_export_reports
from ichnaea.service.error import preprocess_request
from ichnaea.service.submit.schema import (
    ReportSchema,
    SubmitSchema,
)
from ichnaea.tests.base import (
    CeleryAppTestCase,
    TestCase,
)
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)
from ichnaea import util


class SchemaTest(TestCase):

    def _make_request(self, body):
        request = DummyRequest()
        request.body = body
        return request


class TestReportSchema(SchemaTest):

    def test_empty(self):
        schema = ReportSchema()
        request = self._make_request('{}')
        data, errors = preprocess_request(request, schema, response=None)
        self.assertEquals(data['lat'], None)
        self.assertEquals(data['lon'], None)
        self.assertFalse(errors)

    def test_empty_wifi_entry(self):
        schema = ReportSchema()
        wifi = WifiFactory.build()
        request = self._make_request(
            '{"lat": %s, "lon": %s, "wifi": [{}]}' % (wifi.lat, wifi.lon))
        data, errors = preprocess_request(request, schema, response=None)
        self.assertTrue(errors)


class TestSubmitSchema(SchemaTest):

    def test_empty(self):
        schema = SubmitSchema()
        request = self._make_request('{}')
        data, errors = preprocess_request(request, schema, response=None)
        self.assertTrue(errors)

    def test_minimal(self):
        schema = SubmitSchema()
        wifi = WifiFactory.build()
        request = self._make_request(
            '{"items": [{"lat": %s, "lon": %s}]}' % (wifi.lat, wifi.lon))
        data, errors = preprocess_request(request, schema, response=None)
        self.assertFalse(errors)
        self.assertTrue('items' in data)
        self.assertEqual(len(data['items']), 1)


class SubmitTest(CeleryAppTestCase):

    nickname = 'World Tr\xc3\xa4veler'.decode('utf-8')
    email = 'world_tr\xc3\xa4veler@email.com'.decode('utf-8')

    def _post(self, items, api_key=None, status=204, **kw):
        url = '/v1/submit'
        if api_key:
            url += '?key=%s' % api_key
        res = self.app.post_json(url, {'items': items}, status=status, **kw)
        schedule_export_reports.delay().get()
        return res


class TestSubmit(SubmitTest):

    def test_ok_cell(self):
        now = util.utcnow()
        today = now.date()
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0)
        cell = CellFactory.build(radio=Radio.umts)
        res = self._post([{
            'lat': cell.lat,
            'lon': cell.lon,
            'time': now.strftime('%Y-%m-%d'),
            'accuracy': 10,
            'altitude': 123,
            'altitude_accuracy': 7,
            'radio': cell.radio.name,
            'cell': [{
                'radio': cell.radio.name, 'mcc': cell.mcc,
                'mnc': cell.mnc, 'lac': cell.lac, 'cid': cell.cid}],
        }], api_key='test')
        self.assertEqual(res.body, '')

        cell_result = self.session.query(CellObservation).all()
        self.assertEqual(len(cell_result), 1)
        item = cell_result[0]
        self.assertTrue(isinstance(item.report_id, uuid.UUID))
        self.assertEqual(item.created.date(), today)

        self.assertEqual(item.time, first_of_month)
        self.assertEqual(item.lat, cell.lat)
        self.assertEqual(item.lon, cell.lon)
        self.assertEqual(item.accuracy, 10)
        self.assertEqual(item.altitude, 123)
        self.assertEqual(item.altitude_accuracy, 7)
        self.assertEqual(item.radio, cell.radio)
        self.assertEqual(item.mcc, cell.mcc)
        self.assertEqual(item.mnc, cell.mnc)
        self.assertEqual(item.lac, cell.lac)
        self.assertEqual(item.cid, cell.cid)

    def test_ok_wifi(self):
        now = util.utcnow()
        today = now.date()
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0)
        wifi = WifiFactory.build()
        self._post([{
            'lat': wifi.lat,
            'lon': wifi.lon,
            'accuracy': 17,
            'wifi': [{'key': wifi.key.upper(),
                      'signalToNoiseRatio': 5},
                     {'key': '00:34:cd:34:cd:34',
                      'signalToNoiseRatio': 5}],
        }])

        wifi_result = self.session.query(WifiObservation).all()
        self.assertEqual(len(wifi_result), 2)
        item = wifi_result[0]
        report_id = item.report_id
        self.assertTrue(isinstance(report_id, uuid.UUID))
        self.assertEqual(item.created.date(), today)
        self.assertEqual(item.time, first_of_month)
        self.assertEqual(item.lat, wifi.lat)
        self.assertEqual(item.lon, wifi.lon)
        self.assertEqual(item.accuracy, 17)
        self.assertEqual(item.altitude, 0)
        self.assertEqual(item.altitude_accuracy, 0)
        self.assertTrue(item.key in (wifi.key, '0034cd34cd34'))
        self.assertEqual(item.channel, 0)
        self.assertEqual(item.signal, 0)
        self.assertEqual(item.snr, 5)
        item = wifi_result[1]
        self.assertEqual(item.report_id, report_id)
        self.assertEqual(item.created.date(), today)
        self.assertEqual(item.lat, wifi.lat)
        self.assertEqual(item.lon, wifi.lon)

    def test_batches(self):
        batch = 110
        wifis = WifiFactory.build_batch(batch)
        items = [{'lat': wifi.lat,
                  'lon': wifi.lon,
                  'wifi': [{'key': wifi.key}]}
                 for wifi in wifis]

        # add a bad one, this will just be skipped
        items.append({'lat': 10.0, 'lon': 10.0, 'whatever': 'xx'})
        self._post(items)
        self.assertEqual(self.session.query(WifiObservation).count(), batch)

    def test_gzip(self):
        wifi = WifiFactory.build()
        data = {'items': [{'lat': wifi.lat,
                           'lon': wifi.lon,
                           'wifi': [{'key': wifi.key}]}]}
        body = util.encode_gzip(dumps(data))
        headers = {'Content-Encoding': 'gzip'}
        self.app.post(
            '/v1/submit?key=test', body, headers=headers,
            content_type='application/json', status=204)

    def test_mapstat(self):
        wifis = WifiFactory.build_batch(4)
        self._post([
            {'lat': wifis[0].lat,
             'lon': wifis[0].lon,
             'wifi': [{'key': wifis[0].key}]},
            {'lat': wifis[1].lat + 0.00012,
             'lon': wifis[1].lon,
             'wifi': [{'key': wifis[1].key}]},
            {'lat': wifis[1].lat + 0.00013,
             'lon': wifis[1].lon,
             'wifi': [{'key': wifis[2].key}]},
            {'lat': wifis[2].lat * -1.0,
             'lon': wifis[2].lon,
             'wifi': [{'key': wifis[3].key}]},
            {'lat': wifis[3].lat + 1.0,
             'lon': wifis[3].lon,
             'wifi': [{'key': 'invalid'}]},
        ])
        queue = self.celery_app.data_queues['update_mapstat']
        positions = set([(pos['lat'], pos['lon']) for pos in queue.dequeue()])
        self.assertEqual(positions, set([
            (wifis[0].lat, wifis[0].lon),
            (wifis[1].lat + 0.00012, wifis[1].lon),
            (wifis[1].lat + 0.00013, wifis[1].lon),
            (wifis[2].lat * -1.0, wifis[2].lon),
        ]))

    def test_scores(self):
        wifis = WifiFactory.build_batch(3)
        self._post([
            {'lat': wifis[0].lat,
             'lon': wifis[0].lon,
             'wifi': [{'key': wifis[0].key}]},
            {'lat': wifis[1].lat + 1.0,
             'lon': wifis[1].lon,
             'wifi': [{'key': wifis[1].key}]},
            {'lat': wifis[2].lat,
             'lon': wifis[2].lon,
             'wifi': [{'key': 'invalid'}]},
        ], headers={'X-Nickname': self.nickname.encode('utf-8')})

        users = self.session.query(User).all()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].nickname, self.nickname)
        user = users[0]

        queue = self.celery_app.data_queues['update_score']
        scores = {}
        for value in queue.dequeue():
            scores[value['hashkey']] = value['value']

        expected = {
            Score.to_hashkey(userid=user.id,
                             key=ScoreKey.location, time=None): 2,
            Score.to_hashkey(userid=user.id,
                             key=ScoreKey.new_wifi, time=None): 2,
        }
        self.assertEqual(scores, expected)


class TestNickname(SubmitTest):

    def _post_one_wifi(self, nickname=None, email=None):
        wifi = WifiFactory.build()
        data = {'lat': wifi.lat, 'lon': wifi.lon, 'wifi': [{'key': wifi.key}]}
        headers = {}
        if nickname:
            headers['X-Nickname'] = nickname.encode('utf-8')
        if email:
            headers['X-Email'] = email.encode('utf-8')
        return self._post([data], headers=headers)

    def test_nickname_header_error(self):
        self._post_one_wifi(nickname='a')
        self.assertEqual(self.session.query(User).count(), 0)
        queue = self.celery_app.data_queues['update_score']
        self.assertEqual(queue.size(), 0)

    def test_email_header(self):
        self._post_one_wifi(nickname=self.nickname, email=self.email)
        result = self.session.query(User).all()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].email, self.email)

    def test_email_header_update(self):
        user = User(nickname=self.nickname, email=self.email)
        self.session.add(user)
        self.session.commit()
        self._post_one_wifi(nickname=self.nickname, email='new' + self.email)
        result = self.session.query(User).all()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].email, 'new' + self.email)

    def test_email_header_too_long(self):
        email = 'a' * 255 + '@email.com'
        self._post_one_wifi(nickname=self.nickname, email=email)
        result = self.session.query(User).all()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].email, '')

    def test_email_header_without_nickname(self):
        self._post_one_wifi(email=self.email)
        result = self.session.query(User).all()
        self.assertEqual(len(result), 0)


class TestSubmitErrors(SubmitTest):

    def test_error(self):
        wifi = WifiFactory.build()
        res = self.app.post_json(
            '/v1/submit',
            [{'lat': wifi.lat, 'lon': wifi.lon, 'cell': []}],
            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertFalse('status' in res.json)
        self.check_raven(['JSONError'])

    def test_ignore_unknown_json_key(self):
        wifi = WifiFactory.build()
        self._post([{'lat': wifi.lat, 'lon': wifi.lon, 'foo': 1}])

    def test_error_no_mapping(self):
        res = self.app.post_json('/v1/submit', [1], status=400)
        self.assertTrue('errors' in res.json)

    def test_many_errors(self):
        wifi = WifiFactory.build()
        wifis = [{'wrong_key': 'ab'} for i in range(100)]
        res = self._post(
            [{'lat': wifi.lat, 'lon': wifi.lon, 'wifi': wifis}],
            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertTrue(len(res.json['errors']) < 10)
        self.check_raven(['JSONError'])

    def test_no_json(self):
        res = self.app.post('/v1/submit', '\xae', status=400)
        self.assertTrue('errors' in res.json)

    def test_missing_latlon(self):
        wifi = WifiFactory.build()
        self._post([
            {'lat': wifi.lat,
             'lon': wifi.lon,
             'accuracy': 17,
             'wifi': [{'key': wifi.key}],
             },
            {'wifi': [],
             'accuracy': 16},
        ])
        cell_result = self.session.query(CellObservation).all()
        self.assertEqual(len(cell_result), 0)
        wifi_result = self.session.query(WifiObservation).all()
        self.assertEqual(len(wifi_result), 1)

    def test_completely_empty(self):
        res = self.app.post_json('/v1/submit', None, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertTrue(len(res.json['errors']) == 0)


class TestStats(SubmitTest):

    def test_log_no_api_key(self):
        wifi = WifiFactory.build()
        self._post([{'lat': wifi.lat, 'lon': wifi.lon}])
        self.check_stats(counter=['submit.no_api_key'])

    def test_log_unknown_api_key(self):
        wifi = WifiFactory.build()
        self._post(
            [{'lat': wifi.lat, 'lon': wifi.lon}],
            api_key='invalidkey')
        self.check_stats(
            counter=['submit.unknown_api_key',
                     ('submit.api_key.invalidkey', 0)])

    def test_stats(self):
        cell = CellFactory.build()
        wifi = WifiFactory.build()
        self._post([{
            'lat': cell.lat,
            'lon': cell.lon,
            'accuracy': 10,
            'altitude': 123,
            'altitude_accuracy': 7,
            'radio': cell.radio.name,
            'cell': [{
                'radio': cell.radio.name,
                'mcc': cell.mcc,
                'mnc': cell.mnc,
                'lac': cell.lac,
                'cid': cell.cid,
            }],
            'wifi': [{'key': wifi.key}],
        }], api_key='test')

        self.check_stats(
            counter=['items.api_log.test.uploaded.batches',
                     'items.api_log.test.uploaded.reports',
                     'items.api_log.test.uploaded.cell_observations',
                     'items.api_log.test.uploaded.wifi_observations',
                     'items.uploaded.batches',
                     'items.uploaded.reports',
                     'items.uploaded.cell_observations',
                     'items.uploaded.wifi_observations',
                     'submit.api_key.test',
                     'request.v1.submit.204'],
            timer=['items.api_log.test.uploaded.batch_size',
                   'items.uploaded.batch_size',
                   'request.v1.submit',
                   'task.data.insert_measures',
                   'task.data.insert_measures_cell']
        )


class TestRadio(SubmitTest):

    def _query(self):
        cell = CellFactory.build()
        query = {'lat': cell.lat, 'lon': cell.lon,
                 'cell': [{'mcc': cell.mcc, 'mnc': cell.mnc,
                           'lac': cell.lac, 'cid': cell.cid}]}
        return (cell, query)

    def test_missing_radio(self):
        cell, query = self._query()
        self._post([query])
        self.assertEqual(self.session.query(CellObservation).count(), 0)

    def test_missing_radio_in_observation(self):
        cell, query = self._query()
        query['radio'] = cell.radio.name
        self._post([query])
        self.assertEqual(self.session.query(CellObservation).count(), 1)

    def test_missing_radio_top_level(self):
        cell, query = self._query()
        query['cell'][0]['radio'] = cell.radio.name
        self._post([query])
        self.assertEqual(self.session.query(CellObservation).count(), 1)

    def test_invalid_radio(self):
        cell, query = self._query()
        query['cell'][0]['radio'] = '18'
        self._post([query])
        self.assertEqual(self.session.query(CellObservation).count(), 0)
