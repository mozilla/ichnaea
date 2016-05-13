import warnings

from pymysql import err
from sqlalchemy import text

from ichnaea.models.wifi import WifiShard0
from ichnaea.tests.base import DBTestCase


class TestDatabase(DBTestCase):

    def test_constructors(self):
        assert self.db_rw.engine.name == 'mysql'
        assert self.db_ro.engine.name == 'mysql'

    def test_table_creation(self):
        result = self.session.execute('select * from cell_gsm;')
        assert result.first() is None

    def test_show_warnings_backport(self):
        # Fixed in PyMySQL 0.6.7
        stmt = text('DROP TABLE IF EXISTS a; DROP TABLE IF EXISTS b;')
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', err.Warning)
            self.session.execute(stmt)

    def test_executemany_backport(self):
        # Fixed in PyMySQL 0.6.7
        self.session.add(WifiShard0(mac='000000123456'))
        self.session.add(WifiShard0(mac='000000abcdef'))
        self.session.commit()

    def test_excecutemany_on_duplicate(self):
        stmt = WifiShard0.__table__.insert(
            mysql_on_duplicate=u'mac = "\x00\x00\x000\x00\x00", region="\xe4"'
        )
        values = [
            {'mac': '000000100000', 'region': 'DE'},
            {'mac': '000000200000', 'region': u'\xe4'},
            {'mac': '000000200000', 'region': u'\xf6'},
        ]
        self.session.execute(stmt.values(values))
        rows = self.session.query(WifiShard0).all()
        assert (set([row.mac for row in rows]) ==
                set(['000000100000', '000000300000']))
        assert (set([row.region for row in rows]) ==
                set(['DE', u'\xe4']))
