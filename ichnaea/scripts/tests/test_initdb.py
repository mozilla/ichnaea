from ichnaea.scripts import initdb


class TestInitDB(object):

    def test_compiles(self):
        assert hasattr(initdb, 'console_entry')

    def test_db_creds(self):
        creds = initdb._db_creds('mysql+pymysql://user:pwd@localhost/db')
        assert creds == ('user', 'pwd')
