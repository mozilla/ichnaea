from unittest import TestCase

from cornice.pyramidhook import wrap_request
from cornice.schemas import CorniceSchema, validate_colander_schema
from heka.holder import get_client
from pyramid.testing import DummyRequest

from ichnaea.models import (
    Cell,
    CellMeasure,
    Wifi,
)

from ichnaea.backfill.tasks import do_backfill
from ichnaea.tests.base import AppTestCase, find_msg
from ichnaea.tests.base import CeleryTestCase
from sqlalchemy import text


class Event(object):

    def __init__(self, request):
        self.request = request


class TestRequest(DummyRequest):

    def __init__(self, *args, **kw):
        super(TestRequest, self).__init__(*args, **kw)
        wrap_request(Event(self))


class TestSearch(AppTestCase):

    def setUp(self):
        AppTestCase.setUp(self)
        self.heka_client = get_client('ichnaea')
        self.heka_client.stream.msgs.clear()

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
            '/v1/search',
            {"radio": "gsm", "cell": [
                dict(radio="umts", cid=4, **key),
                dict(radio="umts", cid=5, **key),
            ]},
            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "ok", "lat": 1.0010000, '
                                   '"lon": 1.0020000, "accuracy": 35000}')

        msgs = self.heka_client.stream.msgs
        self.assertEquals(1, len(find_msg(msgs, 'counter', 'http.request')))
        self.assertEquals(1, len(find_msg(msgs, 'timer', 'http.request')))
        self.assertEquals(2, len(msgs))

    def test_ok_wifi(self):
        app = self.app
        session = self.db_slave_session
        wifis = [
            Wifi(key="A1", lat=10000000, lon=10000000),
            Wifi(key="B2", lat=10020000, lon=10040000),
            Wifi(key="C3", lat=None, lon=None),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json('/v1/search',
                            {"wifi": [
                                {"key": "A1"}, {"key": "B2"}, {"key": "C3"},
                            ]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "ok", "lat": 1.0010000, '
                                   '"lon": 1.0020000, "accuracy": 500}')

        msgs = self.heka_client.stream.msgs
        self.assertEquals(1, len(find_msg(msgs, 'counter', 'http.request')))
        self.assertEquals(1, len(find_msg(msgs, 'timer', 'http.request')))
        self.assertEquals(2, len(msgs))

    def test_wifi_too_few_candidates(self):
        app = self.app
        session = self.db_slave_session
        wifis = [
            Wifi(key="A1", lat=10000000, lon=10000000),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json('/v1/search',
                            {"wifi": [
                                {"key": "A1"},
                            ]},
                            status=200)
        self.assertEqual(res.body, '{"status": "not_found"}')

    def test_wifi_too_few_matches(self):
        app = self.app
        session = self.db_slave_session
        wifis = [
            Wifi(key="A1", lat=10000000, lon=10000000),
            Wifi(key="B2", lat=None, lon=None),
        ]
        session.add_all(wifis)
        session.commit()
        res = app.post_json('/v1/search',
                            {"wifi": [
                                {"key": "A1"}, {"key": "B2"}, {"key": "C3"},
                            ]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "not_found"}')

    def test_not_found(self):
        app = self.app
        res = app.post_json('/v1/search',
                            {"cell": [{"mcc": 1, "mnc": 2,
                                       "lac": 3, "cid": 4}]},
                            status=200)
        self.assertEqual(res.content_type, 'application/json')
        self.assertEqual(res.body, '{"status": "not_found"}')

    def test_wifi_not_found(self):
        app = self.app
        res = app.post_json('/v1/search', {"wifi": [
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
            '/v1/search',
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

    def test_error(self):
        app = self.app
        res = app.post_json('/v1/search', {"cell": []}, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)
        self.assertFalse('status' in res.json)

    def test_error_unknown_key(self):
        app = self.app
        res = app.post_json('/v1/search', {"foo": 0}, status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)

    def test_error_no_mapping(self):
        app = self.app
        res = app.post_json('/v1/search', [1], status=400)
        self.assertEqual(res.content_type, 'application/json')
        self.assertTrue('errors' in res.json)

    def test_no_valid_keys(self):
        app = self.app
        res = app.post_json('/v1/search', {"wifi": [
                            {"key": ":"}, {"key": ".-"}]},
                            status=200)
        self.assertEqual(res.body, '{"status": "not_found"}')

    def test_no_json(self):
        app = self.app
        res = app.post('/v1/search', "\xae", status=400)
        self.assertTrue('errors' in res.json)


class TestSearchSchema(TestCase):

    def _make_schema(self):
        from ichnaea.service.search.schema import SearchSchema
        return CorniceSchema.from_colander(SearchSchema)

    def _make_request(self, body):
        request = TestRequest()
        request.body = body
        return request

    def test_empty(self):
        schema = self._make_schema()
        request = self._make_request('{}')
        validate_colander_schema(schema, request)
        self.assertEqual(request.errors, [])
        self.assertEqual(request.validated,
                         {'cell': (), 'wifi': (), 'radio': ''})

    def test_empty_cell_entry(self):
        schema = self._make_schema()
        request = self._make_request('{"cell": [{}]}')
        validate_colander_schema(schema, request)
        self.assertTrue('cell' in request.validated)

    def test_wrong_cell_data(self):
        schema = self._make_schema()
        request = self._make_request(
            '{"cell": [{"mcc": "a", "mnc": 2, "lac": 3, "cid": 4}]}')
        validate_colander_schema(schema, request)
        self.assertTrue(request.errors)


class TestBackfill(CeleryTestCase):

    def setUp(self):
        CeleryTestCase.setUp(self)
        self.heka_client = get_client('ichnaea')

    def test_do_backfill(self):
        session = self.db_master_session

        # These are our reference towers that will be used to match
        # similiar towers
        data = [
                # These are measurements for tower A
                CellMeasure(lat=378304721, lon=-1222828703, radio=2,
                            lac=56955, cid=5286246, mcc=310, mnc=410, psc=38,
                            accuracy=20),
                CellMeasure(lat=378392480, lon=-1222648891, radio=2,
                            lac=56955, cid=5286246, mcc=310, mnc=410, psc=38,
                            accuracy=20),

                # These are measurements for tower B
                CellMeasure(lat=20, lon=-10, radio=3,
                            lac=20, cid=31, mcc=310, mnc=410, psc=38,
                            accuracy=20),
                CellMeasure(lat=40, lon=-30, radio=3,
                            lac=20, cid=31, mcc=310, mnc=410, psc=38,
                            accuracy=20),
                ]

        session.add_all(data)

        # This is tower C and should map back to tower A
        session.add_all([CellMeasure(lat=378409925, lon=-1222633523, radio=2,
                                     lac=-1, cid=-1, mcc=310, mnc=410, psc=38,
                                     accuracy=20)])

        # This is tower D and should map back to tower b
        session.add_all([CellMeasure(lat=30, lon=-20, radio=3,
                                     lac=-1, cid=-1, mcc=310, mnc=410, psc=38,
                                     accuracy=20)])

        # This is tower E and should not map back to anything as the
        # radio doesn't match up
        session.add_all([CellMeasure(lat=30, lon=-20, radio=0,
                                     lac=-1, cid=-1, mcc=310, mnc=410, psc=38,
                                     accuracy=20)])

        session.commit()
        do_backfill.delay()

        # check that tower C was mapped correctly
        rset = session.execute(text("select * from cell_measure where radio = 2 and lac = 56955 and cid = 5286246"))
        rset = list(rset)
        self.assertEquals(len(rset), 3)
        lat_longs = [(row['lat'], row['lon']) for row in rset]
        assert (378409925, -1222633523) in lat_longs

        # check that tower D was mapped correctly
        rset = session.execute(text("select * from cell_measure where radio = 3 and lac = 20 and cid = 31"))
        rset = list(rset)
        self.assertEquals(len(rset), 3)
        lat_longs = [(row['lat'], row['lon']) for row in rset]
        assert (30, -20) in lat_longs

        # we shouldn't map towers when the known towers have
        # different radios than our incomplete tower records
        rset = session.execute(text("select count(*) from cell_measure where radio = 0 and lac = - 1 and cid = -1"))
        rset = list(rset)
        self.assertEquals(len(rset), 1)

