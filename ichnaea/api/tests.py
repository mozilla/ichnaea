from colander import MappingSchema, String
from pyramid.request import Request

from ichnaea.api import exceptions as api_exceptions
from ichnaea.api.schema import InternalSchemaNode, InternalMapping
from ichnaea.tests.base import TestCase


class TestInternalSchemaNode(TestCase):

    def test_internal_schema_node_uses_internal_name(self):

        class SampleSchema(MappingSchema):
            schema_type = InternalMapping

            input_name = InternalSchemaNode(
                String(), internal_name='output_name')

            def __init__(self, *args, **kwargs):
                super(SampleSchema, self).__init__(*args, **kwargs)

        input_data = {
            'input_name': 'value',
        }

        output_data = SampleSchema().deserialize(input_data)
        self.assertEqual(output_data['output_name'], 'value')
        self.assertFalse('input_name' in output_data)


class TestExceptions(TestCase):

    def _check(self, error, status):
        response = Request.blank('/').get_response(error())
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.status_code, status)
        self.assertEqual(response.json, error.json_body())
        return response

    def test_str(self):
        error = api_exceptions.LocationNotFound
        self.assertEqual(str(error()), '<LocationNotFound>: 404')

    def test_daily_limit(self):
        error = api_exceptions.DailyLimitExceeded
        response = self._check(error, 403)
        self.assertTrue('dailyLimitExceeded' in response.body)

    def test_invalid_apikey(self):
        error = api_exceptions.InvalidAPIKey
        response = self._check(error, 400)
        self.assertTrue('keyInvalid' in response.body)

    def test_location_not_found(self):
        error = api_exceptions.LocationNotFound
        response = self._check(error, 404)
        self.assertTrue('notFound' in response.body)

    def test_location_not_found_v1(self):
        error = api_exceptions.LocationNotFoundV1
        response = self._check(error, 200)
        self.assertEqual(response.json, {'status': 'not_found'})

    def test_parse_error(self):
        error = api_exceptions.ParseError
        response = self._check(error, 400)
        self.assertTrue('parseError' in response.body)
