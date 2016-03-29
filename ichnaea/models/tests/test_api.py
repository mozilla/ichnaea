import uuid

from ichnaea.models.api import ApiKey
from ichnaea.tests.base import DBTestCase


class TestApiKey(DBTestCase):

    def test_fields(self):
        key = uuid.uuid4().hex
        self.session.add(ApiKey(
            valid_key=key, maxreq=10,
            allow_fallback=True, allow_locate=True))
        self.session.flush()

        result = self.session.query(ApiKey).get(key)
        self.assertEqual(result.valid_key, key)
        self.assertEqual(result.maxreq, 10)
        self.assertEqual(result.allow_fallback, True)
        self.assertEqual(result.allow_locate, True)

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

    def test_should_allow(self):
        result = ApiKey(valid_key='foo',
                        allow_fallback=True, allow_locate=False)
        self.assertTrue(result.should_allow('fallback'))
        self.assertFalse(result.should_allow('locate'))
        self.assertTrue(result.should_allow('unknown'))

    def test_should_log(self):
        result = ApiKey(valid_key='foo')
        self.assertTrue(result.should_log('locate'))
        self.assertTrue(result.should_log('region'))
        self.assertTrue(result.should_log('submit'))

    def test_should_not_log(self):
        result = ApiKey(valid_key=None)
        self.assertFalse(result.should_log('locate'))
        self.assertFalse(result.should_log('region'))
        self.assertFalse(result.should_log('submit'))

    def test_str(self):
        result = ApiKey(valid_key='foo')
        self.assertTrue('foo' in str(result))
