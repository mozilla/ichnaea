from sqlalchemy import text

from ichnaea.models.wifi import WifiShard0
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
        result = self.session.execute('select * from cell;')
        self.assertTrue(result.first() is None)

    def test_session_hook(self):
        session = self.session
        result = []

        def hook(session, value, _result=result, **kw):
            _result.append((value, kw))

        session.on_post_commit(hook, 123, foo='bar')
        session.commit()
        self.assertEqual(result, [(123, {'foo': 'bar'})])

    def test_show_warnings_backport(self):
        # Backport from unreleased PyMySQL 0.6.7
        stmt = text('DROP TABLE IF EXISTS a; DROP TABLE IF EXISTS b;')
        self.session.execute(stmt)

    def test_executemany_backport(self):
        # Fixed in PyMySQL 0.6.7
        self.session.add(WifiShard0(mac='000000123456'))
        self.session.add(WifiShard0(mac='000000abcdef'))
        self.session.commit()

    def test_excecutemany_on_duplicate(self):
        stmt = WifiShard0.__table__.insert(
            mysql_on_duplicate=u'mac = "\x00\x00\x000\x00\x00", country="\xe4"'
        )
        values = [
            {'mac': '000000100000', 'country': 'DE'},
            {'mac': '000000200000', 'country': u'\xe4'},
            {'mac': '000000200000', 'country': u'\xf6'},
        ]
        self.session.execute(stmt.values(values))
        rows = self.session.query(WifiShard0).all()
        self.assertEqual(set([row.mac for row in rows]),
                         set(['000000100000', '000000300000']))
        self.assertEqual(set([row.country for row in rows]),
                         set(['DE', u'\xe4']))
