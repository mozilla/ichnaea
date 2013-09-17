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


class TestSchema(TestCase):

    def _make_schema(self):
        from ichnaea.service.submit.schema import MeasureSchema
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
            '{"lat": 12.3456781, "lon": 23.4567892, "wifi": [{}]}')
        validate_colander_schema(schema, request)
        self.assertTrue(request.errors)
