from unittest import TestCase

from pyramid.testing import DummyRequest

from ichnaea.service.error import preprocess_request


class TestMeasureSchema(TestCase):

    def _make_schema(self):
        from ichnaea.service.submit.schema import MeasureSchema
        return MeasureSchema()

    def _make_request(self, body):
        request = DummyRequest()
        request.body = body
        return request

    def test_empty(self):
        schema = self._make_schema()
        request = self._make_request('{}')
        data, errors = preprocess_request(request, schema, response=None)

        # missing lat and lon will default to -1 and be stripped out
        # instead of causing colander to drop the entire batch of
        # records
        self.assertEquals(data['lat'], -1)
        self.assertEquals(data['lon'], -1)

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
