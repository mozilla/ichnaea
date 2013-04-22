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

    def _make_one(self):
        from ichnaea.schema import SearchSchema
        return CorniceSchema.from_colander(SearchSchema)

    def test_empty(self):
        schema = self._make_one()
        request = TestRequest()
        request.body = '{}'
        validate_colander_schema(schema, request)
        self.assertEqual(request.errors, [])
        self.assertEqual(request.validated, {'cell': (), 'wifi': ()})

    def test_empty_cell_entry(self):
        schema = self._make_one()
        request = TestRequest()
        request.body = '{"cell": [{}]}'
        validate_colander_schema(schema, request)
        self.assertTrue(request.errors)

    def test_wrong_cell_data(self):
        schema = self._make_one()
        request = TestRequest()
        request.body = '{"cell": [{"mcc": "a", "mnc": 2, "lac": 3, "cid": 4}]}'
        validate_colander_schema(schema, request)
        self.assertTrue(request.errors)
