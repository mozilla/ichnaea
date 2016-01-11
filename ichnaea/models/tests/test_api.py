from ichnaea.models.api import ApiKey
from ichnaea.tests.base import DBTestCase


class TestApiKey(DBTestCase):

    def test_fields(self):
        self.session.add(ApiKey(
            valid_key='foo-bar', maxreq=10, shortname='foo',
            log_locate=True, log_region=True, log_submit=True,
            allow_fallback=True, allow_locate=True))
        self.session.flush()

        result = self.session.query(ApiKey).get('foo-bar')
        self.assertEqual(result.valid_key, 'foo-bar')
        self.assertEqual(result.maxreq, 10)
        self.assertEqual(result.log_locate, True)
        self.assertEqual(result.log_region, True)
        self.assertEqual(result.log_submit, True)
        self.assertEqual(result.allow_fallback, True)
        self.assertEqual(result.allow_locate, True)
        self.assertEqual(result.shortname, 'foo')

    def test_should_allow(self):
        result = ApiKey(valid_key='foo',
                        allow_fallback=True, allow_locate=False)
        self.assertEqual(result.should_allow('fallback'), True)
        self.assertEqual(result.should_allow('locate'), False)
        self.assertEqual(result.should_allow('unknown'), True)

    def test_should_log(self):
        result = ApiKey(valid_key='foo',
                        log_locate=True, log_region=False, log_submit=None)
        self.assertEqual(result.should_log('locate'), True)
        self.assertEqual(result.should_log('region'), False)
        self.assertEqual(result.should_log('submit'), False)
        self.assertEqual(result.should_log('unknown'), False)
