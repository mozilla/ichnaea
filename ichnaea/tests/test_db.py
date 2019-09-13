class TestDatabase(object):
    def test_constructor(self, db):
        assert db.engine.name == "mysql"
        assert db.engine.dialect.driver == "pymysql"

    def test_transport(self, sync_db):
        assert sync_db.engine.name == "mysql"
        assert sync_db.engine.dialect.driver == "mysqlconnector"

    def test_table_creation(self, session):
        result = session.execute("select * from cell_gsm;")
        assert result.first() is None
