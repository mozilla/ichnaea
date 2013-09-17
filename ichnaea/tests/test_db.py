from ichnaea.tests.base import DBTestCase


class TestDatabase(DBTestCase):

    def test_constructors(self):
        self.assertEqual(self.db_master.engine.name, 'mysql')
        self.assertEqual(self.db_slave.engine.name, 'mysql')

    def test_sessions(self):
        self.assertTrue(
            self.db_master_session.bind.engine is self.db_master.engine)
        self.assertTrue(
            self.db_slave_session.bind.engine is self.db_slave.engine)

    def test_table_creation(self):
        session = self.db_master_session
        result = session.execute('select * from cell;')
        self.assertTrue(result.first() is None)
        result = session.execute('select * from measure;')
        self.assertTrue(result.first() is None)
