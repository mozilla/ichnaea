from ichnaea.models.api import ApiKey
from ichnaea.tests.base import DBTestCase


class TestApiKey(DBTestCase):

    def test_fields(self):
        session = self.session
        session.add(ApiKey(valid_key='foo-bar', maxreq=10, shortname='foo'))
        session.flush()

        query = session.query(ApiKey).filter(ApiKey.valid_key == 'foo-bar')
        result = query.first()
        self.assertEqual(result.valid_key, 'foo-bar')
        self.assertEqual(result.maxreq, 10)
        self.assertEqual(result.shortname, 'foo')
