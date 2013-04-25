from unittest import TestCase

from cornice.pyramidhook import wrap_request
from cornice.schemas import CorniceSchema, validate_colander_schema
from pyramid.testing import DummyRequest


class Event(object):

    def __init__(self, request):
        self.request = request


class TestRequest(DummyRequest):

    def __init__(self, *args, **kw):
        super(TestRequest, self).__init__(*args, **kw)
        wrap_request(Event(self))


class TestSearchSchema(TestCase):

    def _make_schema(self):
        from ichnaea.schema import SearchSchema
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
                         {'cell': (), 'wifi': (), 'radio': 'gsm'})

    def test_empty_cell_entry(self):
        schema = self._make_schema()
        request = self._make_request('{"cell": [{}]}')
        validate_colander_schema(schema, request)
        self.assertTrue(request.errors)

    def test_wrong_cell_data(self):
        schema = self._make_schema()
        request = self._make_request(
            '{"cell": [{"mcc": "a", "mnc": 2, "lac": 3, "cid": 4}]}')
        validate_colander_schema(schema, request)
        self.assertTrue(request.errors)


class TestMeasureSchema(TestCase):

    def _make_schema(self):
        from ichnaea.schema import MeasureSchema
        return CorniceSchema.from_colander(MeasureSchema)

    def _make_request(self, body):
        request = TestRequest()
        request.body = body
        return request

    def test_empty(self):
        schema = self._make_schema()
        request = self._make_request('{}')
        validate_colander_schema(schema, request)
        self.assertTrue(request.errors)

    def test_empty_wifi_entry(self):
        schema = self._make_schema()
        request = self._make_request(
            '{"lat": 12.345678, "lon": 23.456789, "wifi": [{}]}')
        validate_colander_schema(schema, request)
        self.assertTrue(request.errors)
