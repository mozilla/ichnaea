from sqlalchemy import text
from webob.response import gzip_app_iter

from ichnaea.decimaljson import dumps
from ichnaea.heka_logging import RAVEN_ERROR
from ichnaea.models import (
    Cell,
    Wifi,
)
from ichnaea.tests.base import AppTestCase


class TestSearch(AppTestCase):

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
        self.assertEqual(res.body, '{"status": "ok", "lat": 1.0010000, '
                                   '"lon": 1.0020000, "accuracy": 35000}')

        find_msg = self.find_heka_messages
        self.assertEquals(1, len(find_msg('counter', 'http.request')))
        timer_msgs = find_msg('timer', 'http.request')

        self.assertEquals(1, len(timer_msgs))
        msg = timer_msgs[0]
        f = [f for f in msg.fields if f.name == 'url_path'][0]
        self.assertEquals(f.value_string, ['/v1/search'])

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
        self.assertEqual(res.body, '{"status": "ok", "lat": 1.0010000, '
                                   '"lon": 1.0020000, "accuracy": 500}')

        find_msg = self.find_heka_messages
        self.assertEquals(1, len(find_msg('counter', 'http.request')))
        timer_msgs = find_msg('timer', 'http.request')

        self.assertEquals(1, len(timer_msgs))
        msg = timer_msgs[0]
        f = [f for f in msg.fields if f.name == 'url_path'][0]
        self.assertEquals(f.value_string, ['/v1/search'])

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
        self.assertEqual(res.body, '{"status": "not_found"}')

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
        self.assertEqual(res.body, '{"status": "not_found"}')

    def test_wifi_not_closeby(self):
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
        self.assertEqual(res.body, '{"status": "not_found"}')

    def test_not_found(self):
        app = self.app
        res = app.post_json('/v1/search?key=test',
                            {"cell": [{"mcc": 1, "mnc": 2,
                                       "lac": 3, "cid": 4}]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "not_found"}')

    def test_wifi_not_found(self):
        app = self.app
        res = app.post_json('/v1/search?key=test', {"wifi": [
                            {"key": "abcd"}, {"key": "cdef"}]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "not_found"}')

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
        self.assertEqual(res.body, '{"status": "ok", "lat": 1.0010000, '
                                   '"lon": 1.0020000, "accuracy": 35000}')

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
        self.assertEqual(res.body, '{"status": "ok", "lat": 1.0010000, '
                                   '"lon": 1.0020000, "accuracy": 35000}')

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
        self.assertEqual(res.body, '{"status": "not_found"}')

    def test_no_json(self):
        app = self.app
        res = app.post('/v1/search?key=test', "\xae", status=400)
        self.assertTrue('errors' in res.json)

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
        self.assertEqual(res.body, '{"status": "not_found"}')

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
                            status=200)
        self.assertEqual(res.body, '{"status": "not_found"}')


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

        find_msg = self.find_heka_messages
        self.assertEquals(
            len(find_msg('sentry', RAVEN_ERROR, field_name='msg')), 1)
