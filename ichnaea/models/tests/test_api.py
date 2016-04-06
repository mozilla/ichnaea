import uuid

from ichnaea.models.api import ApiKey
from ichnaea.tests.factories import ApiKeyFactory
from ichnaea.tests.base import DBTestCase


class TestApiKey(DBTestCase):

    def test_fields(self):
        key = uuid.uuid4().hex
        self.session.add(ApiKey(
            valid_key=key, maxreq=10,
            allow_fallback=True, allow_locate=True,
            fallback_name='test_fallback',
            fallback_url='https://localhost:9/api?key=k',
            fallback_ratelimit=100,
            fallback_ratelimit_interval=60,
            fallback_cache_expire=86400,
        ))
        self.session.flush()

        result = self.session.query(ApiKey).get(key)
        self.assertEqual(result.valid_key, key)
        self.assertEqual(result.maxreq, 10)
        self.assertEqual(result.allow_fallback, True)
        self.assertEqual(result.allow_locate, True)
        self.assertEqual(result.fallback_name, 'test_fallback')
        self.assertEqual(result.fallback_url, 'https://localhost:9/api?key=k')
        self.assertEqual(result.fallback_ratelimit, 100)
        self.assertEqual(result.fallback_ratelimit_interval, 60)
        self.assertEqual(result.fallback_cache_expire, 86400)

    def test_get(self):
        key = uuid.uuid4().hex
        self.session.add(ApiKey(valid_key=key, shortname='foo'))
        self.session.flush()

        result = ApiKey.get(self.session, key)
        self.assertTrue(isinstance(result, ApiKey))
        # shortname wasn't loaded at first
        self.assertFalse('shortname' in result.__dict__)
        # but is eagerly loaded
        self.assertEqual(result.shortname, 'foo')

    def test_get_miss(self):
        result = ApiKey.get(self.session, 'unknown')
        self.assertTrue(result is None)

    def test_allowed(self):
        api_key = ApiKeyFactory(allow_locate=True)
        self.assertTrue(api_key.allowed('locate'))
        self.assertTrue(api_key.allowed('region'))
        self.assertTrue(api_key.allowed('submit'))
        self.assertTrue(api_key.allowed('unknown') is None)
        self.assertFalse(ApiKeyFactory(allow_locate=None).allowed('locate'))
        self.assertFalse(ApiKeyFactory(allow_locate=False).allowed('locate'))

    def test_can_fallback(self):
        self.assertTrue(ApiKeyFactory(allow_fallback=True).can_fallback())
        self.assertFalse(ApiKeyFactory(allow_fallback=False).can_fallback())
        self.assertFalse(ApiKeyFactory(allow_fallback=None).can_fallback())
        self.assertFalse(ApiKeyFactory(
            allow_fallback=True, fallback_name=None).can_fallback())
        self.assertFalse(ApiKeyFactory(
            allow_fallback=True, fallback_url=None).can_fallback())
        self.assertFalse(ApiKeyFactory(
            allow_fallback=True, fallback_ratelimit=None).can_fallback())
        self.assertTrue(ApiKeyFactory(
            allow_fallback=True, fallback_ratelimit=0).can_fallback())
        self.assertFalse(ApiKeyFactory(
            allow_fallback=True,
            fallback_ratelimit_interval=None).can_fallback())
        self.assertFalse(ApiKeyFactory(
            allow_fallback=True,
            fallback_ratelimit_interval=0).can_fallback())
        self.assertTrue(ApiKeyFactory(
            allow_fallback=True, fallback_cache_expire=None).can_fallback())
        self.assertTrue(ApiKeyFactory(
            allow_fallback=True, fallback_cache_expire=0).can_fallback())

    def test_str(self):
        result = ApiKey(valid_key='foo')
        self.assertTrue('foo' in str(result))
