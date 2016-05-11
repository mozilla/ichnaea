import time

import colander
from pyramid.request import Request

from ichnaea.api import exceptions as api_exceptions
from ichnaea.api.rate_limit import rate_limit_exceeded
from ichnaea.api.schema import RenamingMapping


class TestRenamingMapping(object):

    def test_to_name(self):
        class SampleSchema(colander.MappingSchema):
            schema_type = RenamingMapping

            input_name = colander.SchemaNode(
                colander.String(), to_name='output_name')
            name = colander.SchemaNode(colander.String())

            def __init__(self, *args, **kwargs):
                super(SampleSchema, self).__init__(*args, **kwargs)

        input_data = {
            'input_name': 'foo',
            'name': 'bar',
        }

        output_data = SampleSchema().deserialize(input_data)
        assert output_data['output_name'] == 'foo'
        assert output_data['name'] == 'bar'
        assert 'input_name' not in output_data


class TestExceptions(object):

    def _check(self, error, status,
               json=True, content_type='application/json'):
        response = Request.blank('/').get_response(error())
        assert response.content_type == content_type
        assert response.status_code == status
        if json:
            assert response.json == error.json_body()
        return response

    def test_str(self):
        error = api_exceptions.LocationNotFound
        assert str(error()) == '<LocationNotFound>: 404'

    def test_daily_limit(self):
        error = api_exceptions.DailyLimitExceeded
        response = self._check(error, 403)
        assert 'dailyLimitExceeded' in response.text

    def test_invalid_apikey(self):
        error = api_exceptions.InvalidAPIKey
        response = self._check(error, 400)
        assert 'keyInvalid' in response.text

    def test_location_not_found(self):
        error = api_exceptions.LocationNotFound
        response = self._check(error, 404)
        assert 'notFound' in response.text

    def test_location_not_found_v0(self):
        error = api_exceptions.LocationNotFoundV0
        response = self._check(error, 200)
        assert response.json == {'status': 'not_found'}

    def test_parse_error(self):
        error = api_exceptions.ParseError
        response = self._check(error, 400)
        assert 'parseError' in response.text


class TestLimiter(object):

    def test_limiter_maxrequests(self, redis):
        rate_key = 'apilimit:key_a:v1.geolocate:20150101'
        maxreq = 5
        expire = 1
        for i in range(maxreq):
            assert not rate_limit_exceeded(
                redis,
                rate_key,
                maxreq=maxreq,
                expire=expire,
            )
        assert rate_limit_exceeded(
            redis,
            rate_key,
            maxreq=maxreq,
            expire=expire,
        )

    def test_limiter_expiry(self, redis):
        rate_key = 'apilimit:key_a:v1.geolocate:20150101'
        maxreq = 100
        expire = 1
        assert not rate_limit_exceeded(
            redis,
            rate_key,
            maxreq=maxreq,
            expire=expire,
        )
        time.sleep(1.0)
        assert not rate_limit_exceeded(
            redis,
            rate_key,
            maxreq=maxreq,
            expire=expire,
        )
