from ichnaea.tests.base import DBTestCase
from ichnaea import util


class TestScore(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.content.models import Score
        return Score(**kw)

    def test_constructor(self):
        utcday = util.utcnow().date()
        score = self._make_one()
        self.assertTrue(score.id is None)
        self.assertEqual(score.time, utcday)

    def test_fields(self):
        utcday = util.utcnow().date()
        score = self._make_one(userid=3, time=utcday, value=15)
        score.name = 'location'
        session = self.db_master_session
        session.add(score)
        session.commit()

        result = session.query(score.__class__).first()
        self.assertEqual(result.name, 'location')
        self.assertEqual(result.userid, 3)
        self.assertEqual(result.time, utcday)
        self.assertEqual(result.value, 15)

    def test_property(self):
        score = self._make_one(key=0, value=13)
        session = self.db_master_session
        session.add(score)
        session.commit()

        result = session.query(score.__class__).first()
        self.assertEqual(result.key, 0)
        self.assertEqual(result.name, 'location')


class TestStat(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.content.models import Stat
        return Stat(**kw)

    def test_constructor(self):
        stat = self._make_one()
        self.assertTrue(stat.id is None)

    def test_fields(self):
        utcday = util.utcnow().date()
        stat = self._make_one(key=1, time=utcday, value=13)
        session = self.db_master_session
        session.add(stat)
        session.commit()

        result = session.query(stat.__class__).first()
        self.assertEqual(result.key, 1)
        self.assertEqual(result.time, utcday)
        self.assertEqual(result.value, 13)

    def test_property(self):
        stat = self._make_one(key=1, value=13)
        session = self.db_master_session
        session.add(stat)
        session.commit()

        result = session.query(stat.__class__).first()
        self.assertEqual(result.key, 1)
        self.assertEqual(result.name, 'cell')

        result.name = ''
        self.assertEqual(result.key, -1)


class TestMapStat(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.content.models import MapStat
        return MapStat(**kw)

    def test_constructor(self):
        stat = self._make_one()
        self.assertTrue(stat.time is None)
        self.assertTrue(stat.lat is None)
        self.assertTrue(stat.lon is None)

    def test_fields(self):
        today = util.utcnow().date()
        stat = self._make_one(lat=12345, lon=-23456, time=today)
        session = self.db_master_session
        session.add(stat)
        session.commit()

        result = session.query(stat.__class__).first()
        self.assertEqual(result.lat, 12345)
        self.assertEqual(result.lon, -23456)
        self.assertEqual(result.time, today)


class TestUser(DBTestCase):

    def _make_one(self, **kw):
        from ichnaea.content.models import User
        return User(**kw)

    def test_constructor(self):
        user = self._make_one()
        self.assertTrue(user.id is None)

    def test_fields(self):
        user = self._make_one(nickname=u"World Traveler")
        session = self.db_master_session
        session.add(user)
        session.commit()

        result = session.query(user.__class__).first()
        self.assertEqual(result.nickname, u"World Traveler")
