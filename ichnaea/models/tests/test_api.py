from ichnaea.models.api import ApiKey
from ichnaea.tests.base import DBTestCase


class TestApiKey(DBTestCase):

    def test_fields(self):
        session = self.session
        session.add(ApiKey(
            valid_key='foo-bar', maxreq=10, shortname='foo',
            email='Test <test@test.com>', description='A longer text.'))
        session.flush()

        result = session.query(ApiKey).first()
        self.assertEqual(result.valid_key, 'foo-bar')
        self.assertEqual(result.shortname, 'foo')
        self.assertEqual(result.email, 'Test <test@test.com>')
        self.assertEqual(result.description, 'A longer text.')
