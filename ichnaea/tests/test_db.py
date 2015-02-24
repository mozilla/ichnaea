from ichnaea.tests.base import DBTestCase


class TestDatabase(DBTestCase):

    def test_constructors(self):
        self.assertEqual(self.db_rw.engine.name, 'mysql')
        self.assertEqual(self.db_ro.engine.name, 'mysql')

    def test_sessions(self):
        self.assertTrue(
            self.db_rw_session.bind.engine is self.db_rw.engine)
        self.assertTrue(
            self.db_ro_session.bind.engine is self.db_ro.engine)

    def test_table_creation(self):
        session = self.session
        result = session.execute('select * from cell;')
        self.assertTrue(result.first() is None)

    def test_session_hook(self):
        session = self.session
        result = []

        def hook(session, value, _result=result, **kw):
            _result.append((value, kw))

        session.on_post_commit(hook, 123, foo='bar')
        session.commit()
        self.assertEqual(result, [(123, {'foo': 'bar'})])
