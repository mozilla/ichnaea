from ichnaea.models.content import (
    MapStat,
    Score,
    ScoreKey,
    Stat,
    StatKey,
    User,
)
from ichnaea.tests.base import DBTestCase
from ichnaea import util


class TestMapStat(DBTestCase):

    def test_fields(self):
        today = util.utcnow().date()
        session = self.db_master_session
        session.add(MapStat(lat=12345, lon=-23456, time=today))
        session.flush()

        result = session.query(MapStat).first()
        self.assertEqual(result.lat, 12345)
        self.assertEqual(result.lon, -23456)
        self.assertEqual(result.time, today)


class TestScore(DBTestCase):

    def test_fields(self):
        utcday = util.utcnow().date()
        session = self.db_master_session
        session.add(Score(
            key=ScoreKey.location, userid=3, time=utcday, value=15))
        session.flush()

        result = session.query(Score).first()
        self.assertEqual(result.key, ScoreKey.location)
        self.assertEqual(result.userid, 3)
        self.assertEqual(result.time, utcday)
        self.assertEqual(result.value, 15)

    def test_enum(self):
        session = self.db_master_session
        session.add(Score(key=ScoreKey.location, value=13))
        session.flush()

        result = session.query(Score).first()
        self.assertEqual(result.key, ScoreKey.location)
        self.assertEqual(int(result.key), 0)
        self.assertEqual(result.key.name, 'location')


class TestStat(DBTestCase):

    def test_fields(self):
        utcday = util.utcnow().date()
        session = self.db_master_session
        session.add(Stat(key=StatKey.cell, time=utcday, value=13))
        session.flush()

        result = session.query(Stat).first()
        self.assertEqual(result.key, StatKey.cell)
        self.assertEqual(result.time, utcday)
        self.assertEqual(result.value, 13)

    def test_enum(self):
        session = self.db_master_session
        session.add(Stat(key=StatKey.cell, value=13))
        session.flush()

        result = session.query(Stat).first()
        self.assertEqual(result.key, StatKey.cell)
        self.assertEqual(int(result.key), 1)
        self.assertEqual(result.key.name, 'cell')


class TestUser(DBTestCase):

    def test_fields(self):
        nickname = u'World Tr\xc3\xa4veler'
        email = u'world_tr\xc3\xa4veler@email.com'
        session = self.db_master_session
        session.add(User(nickname=nickname, email=email))
        session.flush()

        result = session.query(User).first()
        self.assertEqual(result.nickname, nickname)
        self.assertEqual(result.email, email)
