import time

from colander import MappingSchema, String
from pyramid.request import Request

from ichnaea.api import exceptions as api_exceptions
from ichnaea.api.rate_limit import rate_limit_exceeded
from ichnaea.api.schema import InternalSchemaNode, InternalMapping
from ichnaea.tests.base import (
    RedisTestCase,
    TestCase,
)


class TestInternalSchemaNode(TestCase):

    def test_internal_name(self):

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

    def _check(self, error, status,
               json=True, content_type='application/json'):
        response = Request.blank('/').get_response(error())
        self.assertEqual(response.content_type, content_type)
        self.assertEqual(response.status_code, status)
        if json:
            self.assertEqual(response.json, error.json_body())
        return response

    def test_str(self):
        error = api_exceptions.LocationNotFound
        self.assertEqual(str(error()), '<LocationNotFound>: 404')

    def test_daily_limit(self):
        error = api_exceptions.DailyLimitExceeded
        response = self._check(error, 403)
        self.assertTrue('dailyLimitExceeded' in response.text)

    def test_invalid_apikey(self):
        error = api_exceptions.InvalidAPIKey
        response = self._check(error, 400)
        self.assertTrue('keyInvalid' in response.text)

    def test_location_not_found(self):
        error = api_exceptions.LocationNotFound
        response = self._check(error, 404)
        self.assertTrue('notFound' in response.text)

    def test_location_not_found_v0(self):
        error = api_exceptions.LocationNotFoundV0
        response = self._check(error, 200)
        self.assertEqual(response.json, {'status': 'not_found'})

    def test_region_not_found_v0(self):
        error = api_exceptions.RegionNotFoundV0
        response = self._check(error, 404)
        self.assertEqual(response.text, 'null')

    def test_region_not_found_v0_js(self):
        error = api_exceptions.RegionNotFoundV0JS
        response = self._check(
            error, 404, json=False, content_type='text/javascript')
        self.assertEqual(response.charset, 'UTF-8')
        self.assertEqual(response.content_length, 0)
        self.assertEqual(response.text, '')

    def test_parse_error(self):
        error = api_exceptions.ParseError
        response = self._check(error, 400)
        self.assertTrue('parseError' in response.text)


class TestLimiter(RedisTestCase):

    def test_limiter_maxrequests(self):
        rate_key = 'apilimit:key_a:v1.geolocate:20150101'
        maxreq = 5
        expire = 1
        for i in range(maxreq):
            self.assertFalse(rate_limit_exceeded(
                self.redis_client,
                rate_key,
                maxreq=maxreq,
                expire=expire,
            ))
        self.assertTrue(rate_limit_exceeded(
            self.redis_client,
            rate_key,
            maxreq=maxreq,
            expire=expire,
        ))

    def test_limiter_expiry(self):
        rate_key = 'apilimit:key_a:v1.geolocate:20150101'
        maxreq = 100
        expire = 1
        self.assertFalse(rate_limit_exceeded(
            self.redis_client,
            rate_key,
            maxreq=maxreq,
            expire=expire,
        ))
        time.sleep(1)
        self.assertFalse(rate_limit_exceeded(
            self.redis_client,
            rate_key,
            maxreq=maxreq,
            expire=expire,
        ))
