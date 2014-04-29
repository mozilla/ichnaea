from sqlalchemy import text
from webob.response import gzip_app_iter

from ichnaea.decimaljson import dumps, loads
from ichnaea.heka_logging import RAVEN_ERROR
from ichnaea.models import (
    ApiKey,
    Cell,
    Wifi,
)
from ichnaea.tests.base import AppTestCase
from ichnaea.service.base import NO_API_KEY
import random


class TestSearch(AppTestCase):

    def setUp(self):
        AppTestCase.setUp(self)
        session = self.db_slave_session
        session.add(ApiKey(valid_key='test'))
        session.add(ApiKey(valid_key='test.test'))
        session.commit()

    def test_ok_cell(self):
        app = self.app
        session = self.db_slave_session
        key = dict(mcc=1, mnc=2, lac=3)
        data = [
            Cell(lat=10000000, lon=10000000, radio=2, cid=4, **key),
            Cell(lat=10020000, lon=10040000, radio=2, cid=5, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm", "cell": [
                dict(radio="umts", cid=4, **key),
                dict(radio="umts", cid=5, **key),
            ]},
            status=200)

        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": 1.0010000, "lon": 1.0020000,
                                    "accuracy": 35000})

        self.check_expected_heka_messages(
            total=4,
            timer=[('http.request', {'url_path': '/v1/search'})],
            counter=[('search.api_key.test', 1),
                     ('search.cell_hit', 1),
                     ('http.request', 1)]
        )

    def test_ok_wifi(self):
        app = self.app
        session = self.db_slave_session
        wifis = [
            Wifi(key="A1", lat=10000000, lon=10000000),
            Wifi(key="B2", lat=10010000, lon=10020000),
            Wifi(key="C3", lat=10020000, lon=10040000),
            Wifi(key="D4", lat=None, lon=None),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json('/v1/search?key=test',
                            {"wifi": [
                                {"key": "A1"}, {"key": "B2"},
                                {"key": "C3"}, {"key": "D4"},
                            ]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": 1.0010000, "lon": 1.0020000,
                                    "accuracy": 500})

        self.check_expected_heka_messages(
            total=4,
            timer=[('http.request', {'url_path': '/v1/search'})],
            counter=[('search.api_key.test', 1),
                     ('search.wifi_hit', 1),
                     ('http.request', 1)]
        )

    def test_wifi_too_few_candidates(self):
        app = self.app
        session = self.db_slave_session
        wifis = [
            Wifi(key="A1", lat=10000000, lon=10000000),
            Wifi(key="B2", lat=10010000, lon=10020000),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json('/v1/search?key=test',
                            {"wifi": [
                                {"key": "A1"}, {"key": "B2"},
                            ]},
                            status=200)
        self.assertEqual(res.json, {"status": "not_found"})

    def test_wifi_too_few_matches(self):
        app = self.app
        session = self.db_slave_session
        wifis = [
            Wifi(key="A1", lat=10000000, lon=10000000),
            Wifi(key="B2", lat=10010000, lon=10020000),
            Wifi(key="C3", lat=None, lon=None),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json('/v1/search?key=test',
                            {"wifi": [
                                {"key": "A1"}, {"key": "B2"}, {"key": "C3"},
                            ]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "not_found"})

    def test_wifi_ignore_outlier(self):
        app = self.app
        session = self.db_slave_session
        wifis = [
            Wifi(key="A1", lat=10000000, lon=10000000),
            Wifi(key="B2", lat=10010000, lon=10020000),
            Wifi(key="C3", lat=10020000, lon=10040000),
            Wifi(key="D4", lat=20000000, lon=20000000),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json('/v1/search?key=test',
                            {"wifi": [
                                {"key": "A1"}, {"key": "B2"},
                                {"key": "C3"}, {"key": "D4"},
                            ]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": 1.0010000, "lon": 1.0020000,
                                    "accuracy": 500})

    def test_wifi_prefer_cluster_with_better_signals(self):
        app = self.app
        session = self.db_slave_session
        wifis = [
            Wifi(key="A1", lat=10000000, lon=10000000),
            Wifi(key="B2", lat=10010000, lon=10020000),
            Wifi(key="C3", lat=10020000, lon=10040000),
            Wifi(key="D4", lat=20000000, lon=20000000),
            Wifi(key="E5", lat=20010000, lon=20020000),
            Wifi(key="F6", lat=20020000, lon=20040000),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json('/v1/search?key=test',
                            {"wifi": [
                                {"key": "A1", "signal": -100},
                                {"key": "D4", "signal": -80},
                                {"key": "B2", "signal": -100},
                                {"key": "E5", "signal": -90},
                                {"key": "C3", "signal": -100},
                                {"key": "F6", "signal": -54},
                            ]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": 2.0010000, "lon": 2.0020000,
                                    "accuracy": 500})

    def test_wifi_find_sparse_high_signal_cluster(self):
        app = self.app
        session = self.db_slave_session
        wifis = [Wifi(key="A%d" % i,
                      lat=10000000 + i * 100,
                      lon=10000000 + i * 120)
                 for i in range(0, 100)]
        wifis += [
            Wifi(key="D4", lat=20000000, lon=20000000),
            Wifi(key="E5", lat=20010000, lon=20020000),
            Wifi(key="F6", lat=20020000, lon=20040000),
        ]
        session.add_all(wifis)
        session.commit()
        measures = [dict(key="A%d" % i,
                         signal=-80)
                    for i in range(0, 100)]
        measures += [
            dict(key="D4", signal=-75),
            dict(key="E5", signal=-74),
            dict(key="F6", signal=-73)
        ]
        random.shuffle(measures)
        res = app.post_json('/v1/search?key=test',
                            {"wifi": measures},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": 2.0010000, "lon": 2.0020000,
                                    "accuracy": 500})

    def test_wifi_only_use_top_three_signals_in_noisy_cluster(self):
        app = self.app
        session = self.db_slave_session
        # all these should wind up in the same cluster since
        # clustering threshold is 500m and the 100 wifis are
        # spaced in increments of (+1m, +1.2m)
        wifis = [Wifi(key="A%d" % i,
                      lat=10000000 + i * 100,
                      lon=10000000 + i * 120)
                 for i in range(0, 100)]
        session.add_all(wifis)
        session.commit()
        measures = [dict(key="A%d" % i,
                         signal=-80)
                    for i in range(3, 100)]
        measures += [
            dict(key="A0", signal=-75),
            dict(key="A1", signal=-74),
            dict(key="A2", signal=-73)
        ]
        random.shuffle(measures)
        res = app.post_json('/v1/search?key=test',
                            {"wifi": measures},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": 1.0000100, "lon": 1.0000120,
                                    "accuracy": 500})

    def test_wifi_not_closeby(self):
        app = self.app
        session = self.db_slave_session
        wifis = [
            Wifi(key="A1", lat=10000000, lon=10000000),
            Wifi(key="B2", lat=10010000, lon=10020000),
            Wifi(key="C3", lat=20020000, lon=20040000),
            Wifi(key="D4", lat=20000000, lon=20000000),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json('/v1/search?key=test',
                            {"wifi": [
                                {"key": "A1"}, {"key": "B2"},
                                {"key": "C3"}, {"key": "D4"},
                            ]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "not_found"})

    def test_not_found(self):
        app = self.app
        res = app.post_json('/v1/search?key=test',
                            {"cell": [{"mcc": 1, "mnc": 2,
                                       "lac": 3, "cid": 4}]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "not_found"})

        self.check_expected_heka_messages(counter=['search.api_key.test',
                                                   'search.miss'])

    def test_wifi_not_found(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {"wifi": [
                            {"key": "abcd"}, {"key": "cdef"}]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "not_found"})

        self.check_expected_heka_messages(counter=['search.api_key.test',
                                                   'search.miss'])

    def test_wifi_not_found_cell_fallback(self):
        app = self.app
        session = self.db_slave_session
        key = dict(mcc=1, mnc=2, lac=3)
        data = [
            Wifi(key="abcd", lat=30000000, lon=30000000),
            Cell(lat=10000000, lon=10000000, radio=2, cid=4, **key),
            Cell(lat=10020000, lon=10040000, radio=2, cid=5, **key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm", "cell": [
                dict(radio="umts", cid=4, **key),
                dict(radio="umts", cid=5, **key),
            ], "wifi": [
                {"key": "abcd"},
                {"key": "cdef"},
            ]},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": 1.0010000, "lon": 1.0020000,
                                    "accuracy": 35000})

    def test_cell_ignore_invalid_lac_cid(self):
        app = self.app
        session = self.db_slave_session

        key = dict(mcc=1, mnc=2, lac=3)
        ignored_key = dict(mcc=1, mnc=2, lac=-1, cid=-1)

        data = [
            Cell(lat=10000000, lon=10000000, radio=2, cid=4, **key),
            Cell(lat=10020000, lon=10040000, radio=2, cid=5, **key),
            Cell(lat=10000000, lon=10000000, radio=2, **ignored_key),
            Cell(lat=10020000, lon=10040000, radio=3, **ignored_key),
        ]
        session.add_all(data)
        session.commit()

        res = app.post_json(
            '/v1/search?key=test',
            {"radio": "gsm", "cell": [
                dict(radio="umts", cid=4, **key),
                dict(radio="umts", cid=5, **key),

                dict(radio="umts", cid=5, mcc=1, mnc=2, lac=-1),
                dict(radio="umts", cid=-1, mcc=1, mnc=2, lac=3),
            ]},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": 1.0010000, "lon": 1.0020000,
                                    "accuracy": 35000})

    def test_geoip_fallback(self):
        app = self.app
        res = app.post_json(
            '/v1/search?key=test',
            {"wifi": [
                {"key": "Porky"}, {"key": "Piggy"},
                {"key": "Davis"}, {"key": "McSnappy"},
            ]},
            extra_environ={'HTTP_X_FORWARDED_FOR': '66.92.181.240'},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "ok",
                                    "lat": 37.5079, "lon": -121.96,
                                    "accuracy": 40000})

        self.check_expected_heka_messages(
            total=4,
            timer=[('http.request', {'url_path': '/v1/search'})],
            counter=[('search.api_key.test', 1),
                     ('search.geoip_hit', 1),
                     ('http.request', 1)]
        )

    def test_error(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {"cell": []}, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertFalse('status' in res.json)

    def test_error_unknown_key(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {"foo": 0}, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)

    def test_error_no_mapping(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', [1], status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)

    def test_no_valid_keys(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {"wifi": [
                            {"key": ":"}, {"key": ".-"}]},
                            status=200)
        self.assertEqual(res.json, {"status": "not_found"})

    def test_no_json(self):
        app = self.app
        res = app.post('/v1/search?key=test.test', "\xae", status=400)
        self.assertTrue('errors' in res.json)

        self.check_expected_heka_messages(counter=[
            'search.api_key.test__test'])

    def test_gzip(self):
        app = self.app
        data = {"cell": [{"mcc": 1, "mnc": 2, "lac": 3, "cid": 4}]}
        body = ''.join(gzip_app_iter(dumps(data)))
        headers = {
            'Content-Encoding': 'gzip',
        }
        res = app.post('/v1/search?key=test', body, headers=headers,
                       content_type='application/json', status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.json, {"status": "not_found"})

    def test_no_api_key(self):
        app = self.app
        session = self.db_slave_session
        wifis = [
            Wifi(key="A1", lat=10000000, lon=10000000, total_measures=9),
            Wifi(key="B2", lat=10010000, lon=10020000, total_measures=9),
            Wifi(key="C3", lat=10020000, lon=10040000, total_measures=9),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json('/v1/search',
                            {"wifi": [
                                {"key": "A1"}, {"key": "B2"},
                                {"key": "C3"}, {"key": "D4"},
                            ]},
                            status=400)
        self.assertEqual(res.json, loads(NO_API_KEY))
        self.check_expected_heka_messages(counter=['search.no_api_key'])


class TestSearchErrors(AppTestCase):
    # this is a standalone class to ensure DB isolation for dropping tables

    def test_database_error(self):
        app = self.app
        session = self.db_slave_session
        stmt = text("drop table wifi;")
        session.execute(stmt)

        try:
            app.post_json('/v1/search?key=test',
                          {"wifi": [
                              {"key": "A1"}, {"key": "B2"},
                              {"key": "C3"}, {"key": "D4"},
                          ]})
        except Exception:
            pass

        self.check_expected_heka_messages(
            sentry=[('msg', RAVEN_ERROR, 1)],
            timer=['http.request'],
            counter=['http.request']
        )
