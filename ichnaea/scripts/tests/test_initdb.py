from ichnaea.scripts import initdb
from ichnaea.tests.base import TestCase


class InitDBTestCase(TestCase):

    def test_compiles(self):
        self.assertTrue(hasattr(initdb, 'console_entry'))

    def test_db_creds(self):
        creds = initdb._db_creds('mysql+pymysql://user:pwd@localhost/db')
        self.assertEqual(creds, ('user', 'pwd'))
