from datetime import (
    date,
    datetime,
)
import pytz

from webob.response import gzip_app_iter

from ichnaea.content.models import (
    MapStat,
    Score,
    SCORE_TYPE,
    User,
)
from ichnaea.logging import RAVEN_ERROR
from ichnaea.models import (
    CellMeasure,
    RADIO_TYPE,
    WifiMeasure,
)
from ichnaea.customjson import dumps
from ichnaea.tests.base import (
    CeleryAppTestCase,
    FRANCE_MCC,
    PARIS_LAT,
    PARIS_LON,
)
from ichnaea import util


class TestSubmit(CeleryAppTestCase):

    def test_ok_cell(self):
        app = self.app
        today = util.utcnow().date()
        month_rounded_today = today.replace(day=1)
        month_rounded_dt = datetime(month_rounded_today.year,
                                    month_rounded_today.month,
                                    month_rounded_today.day)
        month_rounded_dt = month_rounded_dt.replace(tzinfo=pytz.UTC)

        cell_data = [
            {"radio": "umts", "mcc": FRANCE_MCC,
             "mnc": 1, "lac": 2, "cid": 1234}]
        res = app.post_json(
            '/v1/submit?key=test',
            {"items": [{"lat": PARIS_LAT,
                        "lon": PARIS_LON,
                        "accuracy": 10,
                        "altitude": 123,
                        "altitude_accuracy": 7,
                        "radio": "gsm",
                        "cell": cell_data}]},
            status=204)
        self.assertEqual(res.body, '')

        self.check_stats(
            counter=['items.uploaded.batches',
                     'items.uploaded.reports',
                     'request.v1.submit.204',
                     'submit.api_key.test'],
            timer=['items.uploaded.batch_size',
                   'request.v1.submit'],
        )

        session = self.db_master_session
        cell_result = session.query(CellMeasure).all()
        self.assertEqual(len(cell_result), 1)
        item = cell_result[0]
        self.assertTrue(isinstance(item.report_id, bytes))
        self.assertEqual(len(item.report_id), 16)
        self.assertEqual(item.created.date(), today)

        self.assertEqual(item.time, month_rounded_dt)
        self.assertEqual(item.lat, PARIS_LAT)
        self.assertEqual(item.lon, PARIS_LON)
        self.assertEqual(item.accuracy, 10)
        self.assertEqual(item.altitude, 123)
        self.assertEqual(item.altitude_accuracy, 7)
        self.assertEqual(item.radio, RADIO_TYPE['umts'])
        self.assertEqual(item.mcc, FRANCE_MCC)
        self.assertEqual(item.mnc, 1)
        self.assertEqual(item.lac, 2)
        self.assertEqual(item.cid, 1234)

    def test_ok_wifi(self):
        app = self.app
        today = util.utcnow().date()
        wifi_data = [{"key": "0012AB12AB12",
                      "signalToNoiseRatio": 5},
                     {"key": "00:34:cd:34:cd:34",
                      "signalToNoiseRatio": 5}]
        month_rounded_today = today.replace(day=1)
        month_rounded_dt = datetime(month_rounded_today.year,
                                    month_rounded_today.month,
                                    month_rounded_today.day)
        month_rounded_dt = month_rounded_dt.replace(tzinfo=pytz.UTC)

        res = app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3456781,
                                      "lon": 23.4567892,
                                      "accuracy": 17,
                                      "wifi": wifi_data}]},
            status=204)
        self.assertEqual(res.body, '')
        session = self.db_master_session
        wifi_result = session.query(WifiMeasure).all()
        self.assertEqual(len(wifi_result), 2)
        item = wifi_result[0]
        report_id = item.report_id
        self.assertTrue(isinstance(report_id, bytes))
        self.assertEqual(len(report_id), 16)
        self.assertEqual(item.created.date(), today)
        self.assertEqual(item.time, month_rounded_dt)
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

        session = self.db_master_session

        result = session.query(WifiMeasure).all()
        self.assertEqual(len(result), EXPECTED_RECORDS)

    def test_mapstat(self):
        app = self.app
        long_ago = date(2011, 10, 20)
        today = util.utcnow().date()
        session = self.db_master_session
        stats = [
            MapStat(lat=1000, lon=2000, time=long_ago),
            MapStat(lat=2000, lon=3000, time=long_ago),
            MapStat(lat=3000, lon=4000, time=long_ago),
        ]
        session.add_all(stats)
        session.flush()
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0,
                 "lon": 2.0,
                 "wifi": [{"key": "aaaaaaaaaaaa"}]},
                {"lat": 2.0,
                 "lon": 3.0,
                 "wifi": [{"key": "bbbbbbbbbbbb"}]},
                {"lat": 2.0,
                 "lon": 3.0,
                 "wifi": [{"key": "cccccccccccc"}]},
                {"lat": -2.0,
                 "lon": 3.0,
                 "wifi": [{"key": "cccccccccccc"}]},
                {"lat": 10.0,
                 "lon": 10.0,
                 "wifi": [{"key": "invalid"}]},
            ]},
            status=204)
        # check coarse grained stats
        result = session.query(MapStat).all()
        self.assertEqual(len(result), 4)
        self.assertEqual(
            sorted([(int(r.lat), int(r.lon), r.time, r.id) for r in result]),
            [
                (-2000, 3000, today, stats[2].id + 1),
                (1000, 2000, long_ago, stats[0].id),
                (2000, 3000, long_ago, stats[1].id),
                (3000, 4000, long_ago, stats[2].id),
            ]
        )

    def test_nickname_header(self):
        app = self.app
        nickname = 'World Tr\xc3\xa4veler'
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0,
                 "lon": 2.0,
                 "wifi": [{"key": "00aaaaaaaaaa"}]},
                {"lat": 2.0,
                 "lon": 3.0,
                 "wifi": [{"key": "00bbbbbbbbbb"}]},
                {"lat": 10.0,
                 "lon": 10.0,
                 "wifi": [{"key": "invalid"}]},
            ]},
            headers={'X-Nickname': nickname},
            status=204)
        session = self.db_master_session
        result = session.query(User).all()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].nickname, nickname.decode('utf-8'))
        result = session.query(Score).all()
        self.assertEqual(len(result), 2)
        self.assertEqual(set([r.name for r in result]),
                         set(['location', 'new_wifi']))
        for r in result:
            if r.name == 'location':
                self.assertEqual(r.value, 2)
            elif r.name == 'new_wifi':
                self.assertEqual(r.value, 2)

    def test_nickname_header_error(self):
        app = self.app
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0,
                 "lon": 2.0,
                 "wifi": [{"key": "aaaaaaaaaaaa"}]},
            ]},
            headers={'X-Nickname': "a"},
            status=204)
        session = self.db_master_session
        result = session.query(User).all()
        self.assertEqual(len(result), 0)
        result = session.query(Score).all()
        self.assertEqual(len(result), 0)

    def test_nickname_header_update(self):
        app = self.app
        nickname = 'World Tr\xc3\xa4veler'
        utcday = util.utcnow().date()
        session = self.db_master_session
        user = User(nickname=nickname.decode('utf-8'))
        session.add(user)
        session.flush()
        session.add(Score(userid=user.id, key=SCORE_TYPE['location'], value=7))
        session.add(Score(userid=user.id, key=SCORE_TYPE['new_wifi'], value=3))
        session.commit()
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0,
                 "lon": 2.0,
                 "wifi": [{"key": "00AAAAAAAAAA"}]},
            ]},
            headers={'X-Nickname': nickname},
            status=204)
        result = session.query(User).all()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].nickname, nickname.decode('utf-8'))
        result = session.query(Score).all()
        self.assertEqual(len(result), 2)
        self.assertEqual(set([r.name for r in result]),
                         set(['location', 'new_wifi']))
        for r in result:
            if r.name == 'location':
                self.assertEqual(r.value, 8)
                self.assertEqual(r.time, utcday)
            elif r.name == 'new_wifi':
                self.assertEqual(r.value, 4)
                self.assertEqual(r.time, utcday)

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
        session = self.db_master_session
        result = session.query(User).all()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].email, email.decode('utf-8'))

    def test_email_header_update(self):
        app = self.app
        nickname = 'World Tr\xc3\xa4veler'
        old_email = 'world_tr\xc3\xa4veler@email.com'
        new_email = 'world_tr\xc3\xa4veler2@email.com'
        session = self.db_master_session
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
        session = self.db_master_session
        result = session.query(User).all()
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
        session = self.db_master_session
        result = session.query(User).all()
        self.assertEqual(len(result), 0)

    def test_error(self):
        app = self.app
        res = app.post_json(
            '/v1/submit', [{"lat": 12.3, "lon": 23.4, "cell": []}],
            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertFalse('status' in res.json)

        self.check_expected_heka_messages(
            sentry=[('msg', RAVEN_ERROR, 1)]
        )

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
        app = self.app
        cell = [{'radio': '0', 'mcc': 1, 'mnc': 2} for i in range(100)]
        res = app.post_json(
            '/v1/submit', {"items": [{"lat": 1.0, "lon": 2.0, "cell": cell}]},
            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertTrue(len(res.json['errors']) < 10)

        self.check_expected_heka_messages(
            sentry=[('msg', RAVEN_ERROR, 1)]
        )

    def test_no_json(self):
        app = self.app
        res = app.post('/v1/submit', "\xae", status=400)
        self.assertTrue('errors' in res.json)

    def test_gzip(self):
        app = self.app
        data = {"items": [{"lat": 1.0,
                           "lon": 2.0,
                           "wifi": [{"key": "aaaaaaaaaaaa"}]}]}
        body = ''.join(gzip_app_iter(dumps(data)))
        headers = {
            'Content-Encoding': 'gzip',
        }
        res = app.post('/v1/submit?key=test', body, headers=headers,
                       content_type='application/json', status=204)
        self.assertEqual(res.body, '')

    def test_stats(self):
        app = self.app
        cell_data = [
            {"radio": "umts", "mcc": FRANCE_MCC,
             "mnc": 1, "lac": 2, "cid": 1234}]
        res = app.post_json(
            '/v1/submit?key=test',
            {"items": [{"lat": PARIS_LAT,
                        "lon": PARIS_LON,
                        "accuracy": 10,
                        "altitude": 123,
                        "altitude_accuracy": 7,
                        "radio": "gsm",
                        "cell": cell_data}]},
            status=204)
        self.assertEqual(res.body, '')

        self.check_stats(
            counter=['request.v1.submit.204',
                     'items.uploaded.batches',
                     'submit.api_key.test'],
            timer=['request.v1.submit',
                   'task.data.insert_measures',
                   'task.data.insert_measures_cell']
        )

    def test_missing_latlon(self):
        session = self.db_master_session
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

        cell_result = session.query(CellMeasure).all()
        self.assertEqual(len(cell_result), 0)
        wifi_result = session.query(WifiMeasure).all()
        self.assertEqual(len(wifi_result), 1)

    def test_completely_empty(self):
        app = self.app
        res = app.post_json('/v1/submit', None, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertTrue(len(res.json['errors']) == 0)

    def test_missing_radio_in_measure(self):
        app = self.app
        cell_data = [{"mcc": FRANCE_MCC, "mnc": 1, "lac": 2, "cid": 1234}]
        res = app.post_json(
            '/v1/submit', {"items": [{"lat": PARIS_LAT,
                                      "lon": PARIS_LON,
                                      "radio": "gsm",
                                      "cell": cell_data}]},
            status=204)
        self.assertEqual(res.body, '')
        session = self.db_master_session
        cell_result = session.query(CellMeasure).all()
        self.assertEqual(len(cell_result), 0)

        cell_data = [{"mcc": FRANCE_MCC, "mnc": 1, "lac": 2, "cid": 1234},
                     {'radio': 'gsm',
                      "mcc": FRANCE_MCC,
                      "mnc": 1,
                      "lac": 2,
                      "cid": 1234}, ]
        res = app.post_json(
            '/v1/submit', {"items": [{"lat": PARIS_LAT,
                                      "lon": PARIS_LON,
                                      "radio": "gsm",
                                      "cell": cell_data}]},
            status=204)
        self.assertEqual(res.body, '')
        session = self.db_master_session
        cell_result = session.query(CellMeasure).all()
        self.assertEqual(len(cell_result), 1)
        item = cell_result[0]
        self.assertEqual(item.radio, RADIO_TYPE['gsm'])

    def test_missing_radio_top_level(self):
        app = self.app
        cell_data = [{'radio': '',
                      "mcc": 123,
                      "mnc": 1,
                      "lac": 2,
                      "cid": 1234}]
        res = app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3456781,
                                      "lon": 23.4567892,
                                      "radio": "gsm",
                                      "cell": cell_data}]},
            status=204)
        self.assertEqual(res.body, '')
        session = self.db_master_session
        cell_result = session.query(CellMeasure).all()
        self.assertEqual(len(cell_result), 0)
