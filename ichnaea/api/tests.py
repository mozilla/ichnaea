import time

import colander
from pyramid.request import Request

from ichnaea.api.key import (
    get_key,
    Key,
)
from ichnaea.api import exceptions as api_exceptions
from ichnaea.api.rate_limit import rate_limit_exceeded
from ichnaea.api.schema import RenamingMapping
from ichnaea.tests.factories import (
    ApiKeyFactory,
    KeyFactory,
)


class TestKey(object):

    def test_empty(self, session_tracker):
        key = Key()
        assert isinstance(key, Key)
        assert key.valid_key is None
        session_tracker(0)

    def test_get(self, session, session_tracker):
        api_key = ApiKeyFactory()
        session.flush()
        session_tracker(1)

        result = get_key(session, api_key.valid_key)
        assert isinstance(result, Key)
        session_tracker(2)

        # Test get cache
        result2 = get_key(session, api_key.valid_key)
        assert isinstance(result2, Key)
        session_tracker(2)

    def test_get_miss(self, session, session_tracker):
        result = get_key(session, 'unknown')
        assert result is None
        session_tracker(1)

        # Test get cache
        result2 = get_key(session, 'unknown')
        assert result2 is None
        session_tracker(1)

    def test_allowed(self):
        def one(**kw):
            return KeyFactory(**kw)

        key = one(allow_locate=True, allow_region=True, allow_transfer=True)
        assert key.allowed('locate')
        assert key.allowed('region')
        assert key.allowed('submit')
        assert key.allowed('transfer')
        assert key.allowed('unknown') is None

        assert not one(allow_locate=None).allowed('locate')
        assert not one(allow_locate=False).allowed('locate')
        assert not one(allow_region=None).allowed('region')
        assert not one(allow_region=False).allowed('region')
        assert not one(allow_transfer=None).allowed('transfer')

    def test_store_sample(self):
        key = KeyFactory(store_sample_locate=None, store_sample_submit=None)
        assert key.store_sample('locate') is False
        assert key.store_sample('submit') is False
        assert key.store_sample('region') is False
        assert key.store_sample('transfer') is False

        key = KeyFactory(store_sample_locate=0, store_sample_submit=100)
        assert key.store_sample('locate') is False
        assert key.store_sample('submit') is True

        key = KeyFactory(store_sample_locate=50)
        results = []
        for i in range(20):
            results.append(key.store_sample('locate'))
        assert True in results
        assert False in results

    def test_can_fallback(self):
        def one(**kw):
            return KeyFactory(**kw)

        assert one(allow_fallback=True).can_fallback()
        assert not one(allow_fallback=False).can_fallback()
        assert not one(allow_fallback=None).can_fallback()
        assert not (one(
            allow_fallback=True, fallback_name=None).can_fallback())
        assert not (one(
            allow_fallback=True, fallback_url=None).can_fallback())
        assert not (one(
            allow_fallback=True, fallback_ratelimit=None).can_fallback())
        assert (one(
            allow_fallback=True, fallback_ratelimit=0).can_fallback())
        assert not (one(
            allow_fallback=True,
            fallback_ratelimit_interval=None).can_fallback())
        assert not (one(
            allow_fallback=True,
            fallback_ratelimit_interval=0).can_fallback())
        assert (one(
            allow_fallback=True, fallback_cache_expire=None).can_fallback())
        assert (one(
            allow_fallback=True, fallback_cache_expire=0).can_fallback())


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
        if content_type:
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
        assert b'dailyLimitExceeded' in response.body

    def test_invalid_apikey(self):
        error = api_exceptions.InvalidAPIKey
        response = self._check(error, 400)
        assert b'keyInvalid' in response.body

    def test_location_not_found(self):
        error = api_exceptions.LocationNotFound
        response = self._check(error, 404)
        assert b'notFound' in response.body

    def test_location_not_found_v0(self):
        error = api_exceptions.LocationNotFoundV0
        response = self._check(error, 200)
        assert response.json == {'status': 'not_found'}

    def test_parse_error(self):
        error = api_exceptions.ParseError
        response = self._check(error, 400)
        assert b'parseError' in response.body

    def test_upload_success(self):
        error = api_exceptions.UploadSuccess
        response = self._check(error, 200)
        assert response.body == b'{}'

    def test_upload_success_v0(self):
        error = api_exceptions.UploadSuccessV0
        response = self._check(error, 204, json=False, content_type=None)
        assert response.body == b''

    def test_transfer_success(self):
        error = api_exceptions.TransferSuccess
        response = self._check(error, 200)
        assert response.body == b'{}'


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
