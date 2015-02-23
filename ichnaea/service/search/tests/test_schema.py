from unittest import TestCase

from pyramid.testing import DummyRequest

from ichnaea.service.error import preprocess_request


class TestSearchSchema(TestCase):

    def _make_schema(self):
        from ichnaea.service.search.schema import SearchSchema
        return SearchSchema()

    def _make_request(self, body):
        request = DummyRequest()
        request.body = body
        return request

    def test_empty(self):
        schema = self._make_schema()
        request = self._make_request('{}')
        data, errors = preprocess_request(request, schema, response=None)
        self.assertEqual(errors, [])
        self.assertEqual(data,
                         {'cell': (), 'wifi': (), 'radio': None})

    def test_empty_cell_entry(self):
        schema = self._make_schema()
        request = self._make_request('{"cell": [{}]}')
        data, errors = preprocess_request(request, schema, response=None)
        self.assertTrue('cell' in data)

    def test_wrong_cell_data(self):
        schema = self._make_schema()
        request = self._make_request(
            '{"cell": [{"mcc": "a", "mnc": 2, "lac": 3, "cid": 4}]}')
        data, errors = preprocess_request(request, schema, response=None)
        self.assertTrue(errors)
