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
from ichnaea.tests.base import (
    CeleryAppTestCase,
    FRANCE_MCC,
    PARIS_LAT,
    PARIS_LON,
    TestCase,
)
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)
from ichnaea import util


class TestReportSchema(TestCase):

    def _make_schema(self):
        from ichnaea.service.submit.schema import ReportSchema
        return ReportSchema()

    def _make_request(self, body):
        request = DummyRequest()
        request.body = body
        return request

    def test_empty(self):
        schema = self._make_schema()
        request = self._make_request('{}')
        data, errors = preprocess_request(request, schema, response=None)

        # missing lat and lon will default to -255 and be stripped out
        # instead of causing colander to drop the entire batch of
        # records
        self.assertEquals(data['lat'], None)
        self.assertEquals(data['lon'], None)

        self.assertFalse(errors)

    def test_empty_wifi_entry(self):
        schema = self._make_schema()
        request = self._make_request(
            '{"lat": 12.3456781, "lon": 23.4567892, "wifi": [{}]}')
        data, errors = preprocess_request(request, schema, response=None)
        self.assertTrue(errors)


class TestSubmitSchema(TestCase):

    def _make_schema(self):
        from ichnaea.service.submit.schema import SubmitSchema
        return SubmitSchema()

    def _make_request(self, body):
        request = DummyRequest()
        request.body = body
        return request

    def test_empty(self):
        schema = self._make_schema()
        request = self._make_request('{}')
        data, errors = preprocess_request(request, schema, response=None)
        self.assertTrue(errors)

    def test_minimal(self):
        schema = self._make_schema()
        request = self._make_request(
            '{"items": [{"lat": 12.3456781, "lon": 23.4567892}]}')
        data, errors = preprocess_request(request, schema, response=None)
        self.assertFalse(errors)
        self.assertTrue('items' in data)
        self.assertEqual(len(data['items']), 1)


class TestSubmit(CeleryAppTestCase):

    def test_ok_cell(self):
        app = self.app
        now = util.utcnow()
        today = now.date()
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0)

        cell_data = [
            {"radio": Radio.umts.name, "mcc": FRANCE_MCC,
             "mnc": 1, "lac": 2, "cid": 1234}]
        res = app.post_json(
            '/v1/submit?key=test',
            {"items": [{"lat": PARIS_LAT,
                        "lon": PARIS_LON,
                        "time": now.strftime('%Y-%m-%d'),
                        "accuracy": 10,
                        "altitude": 123,
                        "altitude_accuracy": 7,
                        "radio": Radio.gsm.name,
                        "cell": cell_data}]},
            status=204)
        self.assertEqual(res.body, '')
        schedule_export_reports.delay().get()

        session = self.session
        cell_result = session.query(CellObservation).all()
        self.assertEqual(len(cell_result), 1)
        item = cell_result[0]
        self.assertTrue(isinstance(item.report_id, uuid.UUID))
        self.assertEqual(item.created.date(), today)

        self.assertEqual(item.time, first_of_month)
        self.assertEqual(item.lat, PARIS_LAT)
        self.assertEqual(item.lon, PARIS_LON)
        self.assertEqual(item.accuracy, 10)
        self.assertEqual(item.altitude, 123)
        self.assertEqual(item.altitude_accuracy, 7)
        self.assertEqual(item.radio, Radio.umts)
        self.assertEqual(item.mcc, FRANCE_MCC)
        self.assertEqual(item.mnc, 1)
        self.assertEqual(item.lac, 2)
        self.assertEqual(item.cid, 1234)

    def test_ok_wifi(self):
        app = self.app
        now = util.utcnow()
        today = now.date()
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0)

        wifi_data = [{"key": "0012AB12AB12",
                      "signalToNoiseRatio": 5},
                     {"key": "00:34:cd:34:cd:34",
                      "signalToNoiseRatio": 5}]

        res = app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3456781,
                                      "lon": 23.4567892,
                                      "accuracy": 17,
                                      "wifi": wifi_data}]},
            status=204)
        self.assertEqual(res.body, '')
        schedule_export_reports.delay().get()

        session = self.session
        wifi_result = session.query(WifiObservation).all()
        self.assertEqual(len(wifi_result), 2)
        item = wifi_result[0]
        report_id = item.report_id
        self.assertTrue(isinstance(report_id, uuid.UUID))
        self.assertEqual(item.created.date(), today)
        self.assertEqual(item.time, first_of_month)
        self.assertEqual(item.lat, 12.3456781)
        self.assertEqual(item.lon, 23.4567892)
        self.assertEqual(item.accuracy, 17)
        self.assertEqual(item.altitude, 0)
        self.assertEqual(item.altitude_accuracy, 0)
        self.assertTrue(item.key in ("0012ab12ab12", "0034cd34cd34"))
        self.assertEqual(item.channel, 0)
        self.assertEqual(item.signal, 0)
        self.assertEqual(item.snr, 5)
        item = wifi_result[1]
        self.assertEqual(item.report_id, report_id)
        self.assertEqual(item.created.date(), today)
        self.assertEqual(item.lat, 12.3456781)
        self.assertEqual(item.lon, 23.4567892)

    def test_batches(self):
        app = self.app
        EXPECTED_RECORDS = 110
        wifi_data = [{"key": "aaaaaaaaaaaa"}]
        items = [{"lat": 12.34, "lon": 23.45 + i, "wifi": wifi_data}
                 for i in range(EXPECTED_RECORDS)]

        # let's add a bad one, this will just be skipped
        items.append({'lat': 10, 'lon': 10, 'whatever': 'xx'})
        app.post_json('/v1/submit', {"items": items}, status=204)
        schedule_export_reports.delay().get()

        result = self.session.query(WifiObservation).all()
        self.assertEqual(len(result), EXPECTED_RECORDS)

    def test_mapstat(self):
        self.app.post_json(
            '/v1/submit', {'items': [
                {'lat': 1.0,
                 'lon': 2.0,
                 'wifi': [{'key': 'aaaaaaaaaaaa'}]},
                {'lat': 2.00012,
                 'lon': 3.0,
                 'wifi': [{'key': 'bbbbbbbbbbbb'}]},
                {'lat': 2.00023,
                 'lon': 3.0,
                 'wifi': [{'key': 'cccccccccccc'}]},
                {'lat': -2.0,
                 'lon': 3.0,
                 'wifi': [{'key': 'cccccccccccc'}]},
                {'lat': 10.0,
                 'lon': 10.0,
                 'wifi': [{'key': 'invalid'}]},
            ]},
            status=204)
        schedule_export_reports.delay().get()

        # check queued values
        queue = self.celery_app.data_queues['update_mapstat']
        positions = set([(pos['lat'], pos['lon']) for pos in queue.dequeue()])
        self.assertEqual(positions, set([
            (1.0, 2.0), (2.00012, 3.0), (2.00023, 3.0), (-2.0, 3.0)
        ]))

    def test_nickname_header(self):
        nickname = 'World Tr\xc3\xa4veler'
        self.app.post_json(
            '/v1/submit', {'items': [
                {'lat': 1.0,
                 'lon': 2.0,
                 'wifi': [{'key': '00aaaaaaaaaa'}]},
                {'lat': 2.0,
                 'lon': 3.0,
                 'wifi': [{'key': '00bbbbbbbbbb'}]},
                {'lat': 10.0,
                 'lon': 10.0,
                 'wifi': [{'key': 'invalid'}]},
            ]},
            headers={'X-Nickname': nickname},
            status=204)
        schedule_export_reports.delay().get()

        users = self.session.query(User).all()
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0].nickname, nickname.decode('utf-8'))
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

    def test_nickname_header_error(self):
        self.app.post_json(
            '/v1/submit', {'items': [
                {'lat': 1.0,
                 'lon': 2.0,
                 'wifi': [{"key": 'aaaaaaaaaaaa'}]},
            ]},
            headers={'X-Nickname': 'a'},
            status=204)
        schedule_export_reports.delay().get()

        self.assertEqual(self.session.query(User).count(), 0)
        queue = self.celery_app.data_queues['update_score']
        self.assertEqual(queue.size(), 0)

    def test_email_header(self):
        app = self.app
        nickname = 'World Tr\xc3\xa4veler'
        email = 'world_tr\xc3\xa4veler@email.com'
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0,
                 "lon": 2.0,
                 "wifi": [{"key": "00aaaaaaaaaa"}]},
            ]},
            headers={
                'X-Nickname': nickname,
                'X-Email': email,
            },
            status=204)
        schedule_export_reports.delay().get()

        result = self.session.query(User).all()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].email, email.decode('utf-8'))

    def test_email_header_update(self):
        app = self.app
        nickname = 'World Tr\xc3\xa4veler'
        old_email = 'world_tr\xc3\xa4veler@email.com'
        new_email = 'world_tr\xc3\xa4veler2@email.com'
        session = self.session
        user = User(nickname=nickname, email=old_email.decode('utf-8'))
        session.add(user)
        session.flush()
        session.commit()
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0,
                 "lon": 2.0,
                 "wifi": [{"key": "00AAAAAAAAAA"}]},
            ]},
            headers={
                'X-Nickname': nickname,
                'X-Email': new_email,
            },
            status=204)
        schedule_export_reports.delay().get()

        result = session.query(User).all()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].email, new_email.decode('utf-8'))

    def test_email_header_too_long(self):
        app = self.app
        nickname = 'World Tr\xc3\xa4veler'
        email = 'a' * 255 + '@email.com'
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0,
                 "lon": 2.0,
                 "wifi": [{"key": "00aaaaaaaaaa"}]},
            ]},
            headers={
                'X-Nickname': nickname,
                'X-Email': email,
            },
            status=204)
        schedule_export_reports.delay().get()

        result = self.session.query(User).all()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].email, '')

    def test_email_header_without_nickname(self):
        app = self.app
        email = 'world_tr\xc3\xa4veler@email.com'
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0,
                 "lon": 2.0,
                 "wifi": [{"key": "00aaaaaaaaaa"}]},
            ]},
            headers={
                'X-Email': email,
            },
            status=204)
        schedule_export_reports.delay().get()

        result = self.session.query(User).all()
        self.assertEqual(len(result), 0)

    def test_error(self):
        app = self.app
        res = app.post_json(
            '/v1/submit', [{"lat": 12.3, "lon": 23.4, "cell": []}],
            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertFalse('status' in res.json)
        self.check_raven(['JSONError'])

    def test_ignore_unknown_key(self):
        app = self.app
        app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3, "lon": 23.4, "foo": 1}]},
            status=204)

    def test_log_no_api_key(self):
        app = self.app
        app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3, "lon": 23.4}]},
            status=204)

        self.check_stats(counter=['submit.no_api_key'])

    def test_log_unknown_api_key(self):
        app = self.app
        app.post_json(
            '/v1/submit?key=invalidkey',
            {"items": [{"lat": 12.3, "lon": 23.4}]},
            status=204)

        self.check_stats(
            counter=['submit.unknown_api_key',
                     ('submit.api_key.invalidkey', 0)])

    def test_error_no_mapping(self):
        app = self.app
        res = app.post_json('/v1/submit', [1], status=400)
        self.assertTrue('errors' in res.json)

    def test_many_errors(self):
        wifi = WifiFactory.build()
        wifis = [{'wrong_key': 'ab'} for i in range(100)]
        res = self.app.post_json(
            '/v1/submit',
            {'items': [{'lat': wifi.lat, 'lon': wifi.lon, 'wifi': wifis}]},
            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertTrue(len(res.json['errors']) < 10)
        self.check_raven(['JSONError'])

    def test_no_json(self):
        app = self.app
        res = app.post('/v1/submit', "\xae", status=400)
        self.assertTrue('errors' in res.json)

    def test_gzip(self):
        app = self.app
        data = {"items": [{"lat": 1.0,
                           "lon": 2.0,
                           "wifi": [{"key": "aaaaaaaaaaaa"}]}]}
        body = util.encode_gzip(dumps(data))
        headers = {
            'Content-Encoding': 'gzip',
        }
        res = app.post('/v1/submit?key=test', body, headers=headers,
                       content_type='application/json', status=204)
        self.assertEqual(res.body, '')

    def test_stats(self):
        app = self.app
        cell_data = [
            {"radio": Radio.umts.name, "mcc": FRANCE_MCC,
             "mnc": 1, "lac": 2, "cid": 1234}]
        wifi_data = [{"key": "00:34:cd:34:cd:34"}]
        res = app.post_json(
            '/v1/submit?key=test',
            {"items": [{"lat": PARIS_LAT,
                        "lon": PARIS_LON,
                        "accuracy": 10,
                        "altitude": 123,
                        "altitude_accuracy": 7,
                        "radio": Radio.gsm.name,
                        "cell": cell_data,
                        "wifi": wifi_data,
                        }]},
            status=204)
        self.assertEqual(res.body, '')
        schedule_export_reports.delay().get()

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

    def test_missing_latlon(self):
        session = self.session
        app = self.app

        data = [{"lat": 12.3456781,
                 "lon": 23.4567892,
                 "accuracy": 17,
                 "wifi": [{"key": "00:34:cd:34:cd:34"}]},
                {"wifi": [],
                 "accuracy": 16},
                ]

        res = app.post_json('/v1/submit', {"items": data}, status=204)
        self.assertEqual(res.body, '')
        schedule_export_reports.delay().get()

        cell_result = session.query(CellObservation).all()
        self.assertEqual(len(cell_result), 0)
        wifi_result = session.query(WifiObservation).all()
        self.assertEqual(len(wifi_result), 1)

    def test_completely_empty(self):
        app = self.app
        res = app.post_json('/v1/submit', None, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertTrue(len(res.json['errors']) == 0)

    def test_missing_radio_in_observation(self):
        cell = CellFactory.build()
        self.app.post_json(
            '/v1/submit', {'items': [{
                'lat': cell.lat,
                'lon': cell.lon,
                'radio': cell.radio.name,
                'cell': [{
                    'mcc': cell.mcc,
                    'mnc': cell.mnc,
                    'lac': cell.lac,
                    'cid': cell.cid,
                }]
            }]},
            status=204)
        schedule_export_reports.delay().get()

        self.assertEqual(self.session.query(CellObservation).count(), 1)

    def test_missing_radio_top_level(self):
        cell = CellFactory.build()
        self.app.post_json(
            '/v1/submit', {'items': [{
                'lat': cell.lat,
                'lon': cell.lon,
                'cell': [{
                    'radio': cell.radio.name,
                    'mcc': cell.mcc,
                    'mnc': cell.mnc,
                    'lac': cell.lac,
                    'cid': cell.cid,
                }]
            }]},
            status=204)
        schedule_export_reports.delay().get()

        self.assertEqual(self.session.query(CellObservation).count(), 1)

    def test_missing_radio(self):
        cell = CellFactory.build()
        self.app.post_json(
            '/v1/submit', {'items': [{
                'lat': cell.lat,
                'lon': cell.lon,
                'cell': [{
                    'mcc': cell.mcc,
                    'mnc': cell.mnc,
                    'lac': cell.lac,
                    'cid': cell.cid,
                }]
            }]},
            status=204)
        schedule_export_reports.delay().get()

        self.assertEqual(self.session.query(CellObservation).count(), 0)

    def test_invalid_radio(self):
        cell = CellFactory.build()
        self.app.post_json(
            '/v1/submit', {'items': [{
                'lat': cell.lat,
                'lon': cell.lon,
                'cell': [{
                    'radio': '18',
                    'mcc': cell.mcc,
                    'mnc': cell.mnc,
                    'lac': cell.lac,
                    'cid': cell.cid,
                }]
            }]},
            status=204)
        schedule_export_reports.delay().get()

        self.assertEqual(self.session.query(CellObservation).count(), 0)
