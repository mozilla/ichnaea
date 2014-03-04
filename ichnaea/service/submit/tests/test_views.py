from datetime import datetime
from datetime import timedelta

from webob.response import gzip_app_iter

from ichnaea.content.models import (
    MapStat,
    MAPSTAT_TYPE,
    Score,
    SCORE_TYPE,
    User,
)
from ichnaea.models import (
    CellMeasure,
    Measure,
    RADIO_TYPE,
    WifiMeasure,
)
from ichnaea.decimaljson import (
    dumps,
    encode_datetime,
)
from ichnaea.tests.base import CeleryAppTestCase


class TestSubmit(CeleryAppTestCase):

    def test_ok_cell(self):
        app = self.app
        today = datetime.utcnow().date()

        cell_data = [
            {"radio": "umts", "mcc": 123, "mnc": 1, "lac": 2, "cid": 1234}]
        res = app.post_json(
            '/v1/submit?key=test',
            {"items": [{"lat": 12.3456781,
                        "lon": 23.4567892,
                        "accuracy": 10,
                        "altitude": 123,
                        "altitude_accuracy": 7,
                        "radio": "gsm",
                        "cell": cell_data}]},
            status=204)
        self.assertEqual(res.body, '')

        find_msg = self.find_heka_messages
        self.assertEqual(1, len(find_msg('counter', 'http.request')))
        self.assertEqual(1, len(find_msg('counter', 'submit.api_key.test')))

        session = self.db_master_session
        measure_result = session.query(Measure).all()
        self.assertEqual(len(measure_result), 1)

        cell_result = session.query(CellMeasure).all()
        self.assertEqual(len(cell_result), 1)
        item = cell_result[0]
        self.assertEqual(item.measure_id, measure_result[0].id)
        self.assertEqual(item.created.date(), today)
        self.assertEqual(item.lat, 123456781)
        self.assertEqual(item.lon, 234567892)
        self.assertEqual(item.accuracy, 10)
        self.assertEqual(item.altitude, 123)
        self.assertEqual(item.altitude_accuracy, 7)
        self.assertEqual(item.radio, RADIO_TYPE['umts'])
        self.assertEqual(item.mcc, 123)
        self.assertEqual(item.mnc, 1)
        self.assertEqual(item.lac, 2)
        self.assertEqual(item.cid, 1234)

    def test_ok_cell_radio(self):
        app = self.app
        cell_data = [{"mcc": 123, "mnc": 1, "lac": 2, "cid": 1234}]
        res = app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3456781,
                                      "lon": 23.4567892,
                                      "radio": "gsm",
                                      "cell": cell_data}]},
            status=204)
        self.assertEqual(res.body, '')
        session = self.db_master_session
        measure_result = session.query(Measure).all()
        self.assertEqual(len(measure_result), 1)

        cell_result = session.query(CellMeasure).all()
        self.assertEqual(len(cell_result), 1)
        item = cell_result[0]
        self.assertEqual(item.measure_id, measure_result[0].id)
        self.assertEqual(item.radio, RADIO_TYPE['gsm'])

    def test_ok_wifi(self):
        app = self.app
        today = datetime.utcnow().date()
        wifi_data = [{"key": "0012AB12AB12"}, {"key": "00:34:cd:34:cd:34"}]
        res = app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3456781,
                                      "lon": 23.4567892,
                                      "accuracy": 17,
                                      "wifi": wifi_data}]},
            status=204)
        self.assertEqual(res.body, '')
        session = self.db_master_session
        measure_result = session.query(Measure).all()
        self.assertEqual(len(measure_result), 1)
        item = measure_result[0]

        wifi_result = session.query(WifiMeasure).all()
        self.assertEqual(len(wifi_result), 2)
        item = wifi_result[0]
        self.assertEqual(item.measure_id, measure_result[0].id)
        self.assertEqual(item.created.date(), today)
        self.assertEqual(item.lat, 123456781)
        self.assertEqual(item.lon, 234567892)
        self.assertEqual(item.accuracy, 17)
        self.assertEqual(item.altitude, 0)
        self.assertEqual(item.altitude_accuracy, 0)
        self.assertTrue(item.key in ("0012ab12ab12", "0034cd34cd34"))
        self.assertEqual(item.channel, 0)
        self.assertEqual(item.signal, 0)
        item = wifi_result[1]
        self.assertEqual(item.measure_id, measure_result[0].id)
        self.assertEqual(item.created.date(), today)
        self.assertEqual(item.lat, 123456781)
        self.assertEqual(item.lon, 234567892)

    def test_ok_wifi_frequency(self):
        app = self.app
        wifi_data = [
            {"key": "009999999999"},
            {"key": "00aaaaaaaaaa", "frequency": 2427},
            {"key": "00bbbbbbbbbb", "channel": 7},
            {"key": "00cccccccccc", "frequency": 5200},
            {"key": "00dddddddddd", "frequency": 5700},
            {"key": "00eeeeeeeeee", "frequency": 3100},
            {"key": "00fffffffffa", "frequency": 2412, "channel": 9},
        ]
        res = app.post_json(
            '/v1/submit', {"items": [{"lat": 12.345678,
                                      "lon": 23.456789,
                                      "wifi": wifi_data}]},
            status=204)
        self.assertEqual(res.body, '')
        session = self.db_master_session

        result = session.query(WifiMeasure).all()
        self.assertEqual(len(result), 7)

        wifis = dict([(w.key, w.channel) for w in result])
        self.assertEqual(wifis['009999999999'], 0)
        self.assertEqual(wifis['00aaaaaaaaaa'], 4)
        self.assertEqual(wifis['00bbbbbbbbbb'], 7)
        self.assertEqual(wifis['00cccccccccc'], 40)
        self.assertEqual(wifis['00dddddddddd'], 140)
        self.assertEqual(wifis['00eeeeeeeeee'], 0)
        self.assertEqual(wifis['00fffffffffa'], 9)

    def test_batches(self):
        app = self.app
        wifi_data = [{"key": "aaaaaaaaaaaa"}, {"key": "bbbbbbbbbbbb"}]
        items = [{"lat": 12.34, "lon": 23.45 + i, "wifi": wifi_data}
                 for i in range(10)]
        res = app.post_json('/v1/submit', {"items": items}, status=204)
        self.assertEqual(res.body, '')

        # let's add a bad one
        items.append({'whatever': 'xx'})
        res = app.post_json('/v1/submit', {"items": items}, status=400)

    def test_time(self):
        app = self.app
        # test two weeks ago and "now"
        time = (datetime.utcnow() - timedelta(14)).replace(microsecond=0)
        tday = time.replace(hour=0, minute=0, second=0)
        tstr = encode_datetime(time)
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0,
                 "lon": 2.0,
                 "wifi": [{"key": "00aaaaaaaaaa"}],
                 "time": tstr},
                {"lat": 2.0,
                 "lon": 3.0,
                 "wifi": [{"key": "00bbbbbbbbbb"}]},
            ]},
            status=204)
        session = self.db_master_session
        result = session.query(WifiMeasure).all()
        self.assertEqual(len(result), 2)

        wifis = dict([(w.key, (w.created, w.time)) for w in result])
        today = datetime.utcnow().date()

        self.assertEqual(wifis['00aaaaaaaaaa'][0].date(), today)
        self.assertEqual(wifis['00aaaaaaaaaa'][1], tday)

        self.assertEqual(wifis['00bbbbbbbbbb'][0].date(), today)
        self.assertEqual(wifis['00bbbbbbbbbb'][1].date(), today)

    def test_time_short_format(self):
        app = self.app
        # a string like "2014-01-15"
        time = datetime.utcnow().date()
        tstr = time.isoformat()
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0,
                 "lon": 2.0,
                 "wifi": [{"key": "00aaaaaaaaaa"}], "time": tstr},
            ]},
            status=204)
        session = self.db_master_session
        result = session.query(WifiMeasure).all()
        self.assertEqual(len(result), 1)
        result_time = result[0].time
        self.assertEqual(result_time.date(), time)
        self.assertEqual(result_time.hour, 0)
        self.assertEqual(result_time.minute, 0)
        self.assertEqual(result_time.second, 0)
        self.assertEqual(result_time.microsecond, 0)

    def test_time_future(self):
        app = self.app
        time = "2070-01-01T11:12:13.456Z"
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0,
                 "lon": 2.0,
                 "wifi": [{"key": "00aaaaaaaaaa"}],
                 "time": time},
            ]},
            status=204)
        session = self.db_master_session
        result = session.query(WifiMeasure).all()
        self.assertEqual(len(result), 1)
        self.assertNotEqual(result[0].time.year, 2070)

    def test_time_past(self):
        app = self.app
        time = "2011-01-01T11:12:13.456Z"
        app.post_json(
            '/v1/submit', {"items": [
                {"lat": 1.0,
                 "lon": 2.0,
                 "wifi": [{"key": "00aaaaaaaaaa"}], "time": time},
            ]},
            status=204)
        session = self.db_master_session
        result = session.query(WifiMeasure).all()
        self.assertEqual(len(result), 1)
        self.assertNotEqual(result[0].time, 2011)

    def test_mapstat(self):
        app = self.app
        session = self.db_master_session
        key_10m = MAPSTAT_TYPE['location']
        key_100m = MAPSTAT_TYPE['location_100m']
        session.add_all([
            MapStat(lat=10000, lon=20000, key=key_10m, value=13),
            MapStat(lat=10000, lon=30000, key=key_10m, value=1),
            MapStat(lat=20000, lon=30000, key=key_10m, value=3),
            MapStat(lat=20000, lon=40000, key=key_10m, value=1),
            MapStat(lat=1000, lon=2000, key=key_100m, value=7),
            MapStat(lat=1000, lon=3000, key=key_100m, value=2),
            MapStat(lat=2000, lon=3000, key=key_100m, value=5),
            MapStat(lat=2000, lon=4000, key=key_100m, value=9),
        ])
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
            ]},
            status=204)
        # check fine grained stats
        result = session.query(MapStat).filter(
            MapStat.key == MAPSTAT_TYPE['location']).all()
        self.assertEqual(len(result), 5)
        self.assertEqual(
            sorted([(int(r.lat), int(r.lon), int(r.value)) for r in result]),
            [
                (-20000, 30000, 1),
                (10000, 20000, 14),
                (10000, 30000, 1),
                (20000, 30000, 5),
                (20000, 40000, 1),
            ]
        )
        # check coarse grained stats
        result = session.query(MapStat).filter(
            MapStat.key == MAPSTAT_TYPE['location_100m']).all()
        self.assertEqual(len(result), 5)
        self.assertEqual(
            sorted([(int(r.lat), int(r.lon), int(r.value)) for r in result]),
            [
                (-2000, 3000, 1),
                (1000, 2000, 8),
                (1000, 3000, 2),
                (2000, 3000, 7),
                (2000, 4000, 9),
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
            ]},
            headers={'X-Nickname': nickname},
            status=204)
        session = self.db_master_session
        result = session.query(User).all()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].nickname, nickname.decode('utf-8'))
        result = session.query(Score).all()
        self.assertEqual(len(result), 3)
        self.assertEqual(set([r.name for r in result]),
                         set(['location', 'new_location', 'new_wifi']))
        for r in result:
            if r.name == 'location':
                self.assertEqual(r.value, 2)
            elif r.name == 'new_location':
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
        utcday = datetime.utcnow().date()
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
        self.assertEqual(len(result), 3)
        self.assertEqual(set([r.name for r in result]),
                         set(['location', 'new_location', 'new_wifi']))
        for r in result:
            if r.name == 'location':
                self.assertEqual(r.value, 8)
                self.assertEqual(r.time, utcday)
            elif r.name == 'new_location':
                self.assertEqual(r.value, 1)
                self.assertEqual(r.time, utcday)
            elif r.name == 'new_wifi':
                self.assertEqual(r.value, 4)
                self.assertEqual(r.time, utcday)

    def test_error(self):
        app = self.app
        res = app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3, "lon": 23.4, "cell": []}]},
            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertFalse('status' in res.json)

    def test_error_unknown_key(self):
        app = self.app
        res = app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3, "lon": 23.4, "foo": 1}]},
            status=400)
        self.assertTrue('errors' in res.json)

    def test_error_no_api_key(self):
        app = self.app
        res = app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3, "lon": 23.4}]},
            status=400)
        self.assertTrue('errors' in res.json)

        find_msg = self.find_heka_messages
        self.assertEqual(1, len(find_msg('counter', 'submit.no_api_key')))

    def test_error_no_mapping(self):
        app = self.app
        res = app.post_json('/v1/submit', [1], status=400)
        self.assertTrue('errors' in res.json)

    def test_error_too_short_wifi_key(self):
        app = self.app
        wifi_data = [{"key": "ab:12:34:56:78:90"}, {"key": "cd:34"}]
        app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3456781,
                                      "lon": 23.4567892,
                                      "wifi": wifi_data}]},
            status=204)
        session = self.db_master_session
        result = session.query(WifiMeasure).all()
        # if any of the keys is too short, the entire batch gets rejected
        self.assertEqual(len(result), 0)

    def test_error_too_long_wifi_key(self):
        app = self.app
        wifi_data = [{"key": "ab:12:34:56:78:90"}, {"key": "cd:34" * 10}]
        app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3456781,
                                      "lon": 23.4567892,
                                      "wifi": wifi_data}]},
            status=204)
        session = self.db_master_session
        result = session.query(WifiMeasure).all()
        # if any of the keys is too long, the entire batch gets rejected
        self.assertEqual(len(result), 0)

    def test_many_errors(self):
        app = self.app
        cell = [{'radio': '0', 'mcc': 1, 'mnc': 2} for i in range(100)]
        res = app.post_json(
            '/v1/submit', {"items": [{"lat": 1.0, "lon": 2.0, "cell": cell}]},
            status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertTrue(len(res.json['errors']) < 10)

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

    def test_heka_logging(self):
        app = self.app
        cell_data = [
            {"radio": "umts", "mcc": 123, "mnc": 1, "lac": 2, "cid": 1234}]
        res = app.post_json(
            '/v1/submit?key=test',
            {"items": [{"lat": 12.3456781,
                        "lon": 23.4567892,
                        "accuracy": 10,
                        "altitude": 123,
                        "altitude_accuracy": 7,
                        "radio": "gsm",
                        "cell": cell_data}]},
            status=204)
        self.assertEqual(res.body, '')

        """
        We should be capturing 4 metrics:
        1) counter for URL request
        2) counter for items.uploaded
        3) timer to respond
        4) timer for "insert_cell_measure"
        5) timer for "insert_measures"
        """

        find_msg = self.find_heka_messages
        self.assertEqual(1, len(find_msg('counter', 'http.request')))
        self.assertEqual(1, len(find_msg('counter', 'items.uploaded')))
        self.assertEqual(1, len(find_msg('counter', 'submit.api_key.test')))
        self.assertEqual(1, len(find_msg('timer', 'http.request')))
        taskname = 'task.service.submit.insert_cell_measures'
        self.assertEqual(1, len(find_msg('timer', taskname)))
        taskname = 'task.service.submit.insert_measures'
        self.assertEqual(1, len(find_msg('timer', taskname)))

    def test_bad_wifi_keys(self):
        app = self.app
        # we ban f{12}
        wifi_data = [{"key": "FFFFFFFFFFFF"}]
        app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3456781,
                                      "lon": 23.4567892,
                                      "accuracy": 17,
                                      "wifi": wifi_data}]},
            status=204)

        session = self.db_master_session
        result = session.query(WifiMeasure).all()
        self.assertEqual(len(result), 0)

        # we ban 0{12}
        wifi_data = [{"key": "00:00:00:00:00:00"}]
        app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3456781,
                                      "lon": 23.4567892,
                                      "accuracy": 17,
                                      "wifi": wifi_data}]},
            status=204)

        session = self.db_master_session
        result = session.query(WifiMeasure).all()
        self.assertEqual(len(result), 0)

        # we ban any locally administered wifi key based on the U/L
        # bit https://en.wikipedia.org/wiki/MAC_address
        wifi_data = [{"key": "0a:00:00:00:00:00"}]
        app.post_json(
            '/v1/submit', {"items": [{"lat": 12.3456781,
                                      "lon": 23.4567892,
                                      "accuracy": 17,
                                      "wifi": wifi_data}]},
            status=204)

        session = self.db_master_session
        result = session.query(WifiMeasure).all()
        self.assertEqual(len(result), 0)
