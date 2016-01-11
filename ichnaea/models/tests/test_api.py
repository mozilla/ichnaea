from ichnaea.models.api import ApiKey
from ichnaea.tests.base import DBTestCase


class TestApiKey(DBTestCase):

    def test_fields(self):
        session = self.session
        session.add(ApiKey(
            valid_key='foo-bar', maxreq=10, shortname='foo',
            log_locate=True, log_region=True, log_submit=True,
            allow_fallback=True, allow_locate=True))
        session.flush()

        result = session.query(ApiKey).get('foo-bar')
        self.assertEqual(result.valid_key, 'foo-bar')
        self.assertEqual(result.maxreq, 10)
        self.assertEqual(result.log_locate, True)
        self.assertEqual(result.log_region, True)
        self.assertEqual(result.log_submit, True)
        self.assertEqual(result.allow_fallback, True)
        self.assertEqual(result.allow_locate, True)
        self.assertEqual(result.shortname, 'foo')

        self.assertEqual(result.should_log('locate'), True)
        self.assertEqual(result.should_log('unknown'), False)
