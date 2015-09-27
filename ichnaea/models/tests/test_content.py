from ichnaea.models.content import (
    decode_datamap_grid,
    encode_datamap_grid,
    DataMap,
    MapStat,
    Score,
    ScoreKey,
    Stat,
    StatKey,
    User,
)
from ichnaea.tests.base import (
    DBTestCase,
    TestCase,
)
from ichnaea import util


class TestDataMapCodec(TestCase):

    def test_decode_datamap_grid(self):
        self.assertEqual(
            decode_datamap_grid(b'\x00\x00\x00\x00\x00\x00\x00\x00'), (0, 0))
        self.assertEqual(
            decode_datamap_grid(b'AAAAAAAAAAA=', codec='base64'), (0, 0))
        self.assertEqual(
            decode_datamap_grid(b'\x00\x01_\x90\x00\x02\xbf '),
            (90000, 180000))
        self.assertEqual(
            decode_datamap_grid(b'AAFfkAACvyA=', codec='base64'),
            (90000, 180000))
        self.assertEqual(
            decode_datamap_grid(b'\xff\xfe\xa0p\xff\xfd@\xe0'),
            (-90000, -180000))
        self.assertEqual(
            decode_datamap_grid(b'//6gcP/9QOA=', codec='base64'),
            (-90000, -180000))

    def test_encode_datamap_grid(self):
        self.assertEqual(encode_datamap_grid(0, 0),
                         b'\x00\x00\x00\x00\x00\x00\x00\x00')
        self.assertEqual(encode_datamap_grid(0, 0, codec='base64'),
                         b'AAAAAAAAAAA=')

        self.assertEqual(encode_datamap_grid(90.0, 180.0, scale=True),
                         b'\x00\x01_\x90\x00\x02\xbf ')
        self.assertEqual(encode_datamap_grid(90000, 180000),
                         b'\x00\x01_\x90\x00\x02\xbf ')
        self.assertEqual(encode_datamap_grid(90000, 180000, codec='base64'),
                         b'AAFfkAACvyA=')

        self.assertEqual(encode_datamap_grid(-90000, -180000),
                         b'\xff\xfe\xa0p\xff\xfd@\xe0')
        self.assertEqual(encode_datamap_grid(-90000, -180000, codec='base64'),
                         b'//6gcP/9QOA=')


class TestDataMap(DBTestCase):

    def test_fields(self):
        today = util.utcnow().date()
        self.session.add(DataMap(grid=(12345, -23456),
                                 created=today, modified=today))
        self.session.flush()
        result = self.session.query(DataMap).first()
        self.assertEqual(result.grid, (12345, -23456))
        self.assertEqual(result.created, today)
        self.assertEqual(result.modified, today)

    def test_scale(self):
        self.assertEqual(DataMap.scale(-1.12345678, 2.23456789),
                         (-1123, 2235))

    def test_grid_bytes(self):
        grid = encode_datamap_grid(12000, 34000)
        self.session.add(DataMap(grid=grid))
        self.session.flush()
        result = self.session.query(DataMap).first()
        self.assertEqual(result.grid, (12000, 34000))

    def test_grid_none(self):
        self.session.add(DataMap(grid=None))
        with self.assertRaises(Exception):
            self.session.flush()

    def test_grid_length(self):
        self.session.add(DataMap(grid=b'\x00' * 9))
        with self.assertRaises(Exception):
            self.session.flush()

    def test_grid_list(self):
        self.session.add(DataMap(grid=[1000, -2000]))
        with self.assertRaises(Exception):
            self.session.flush()


class TestMapStat(DBTestCase):

    def test_fields(self):
        today = util.utcnow().date()
        self.session.add(MapStat(lat=12345, lon=-23456, time=today))
        self.session.flush()

        result = self.session.query(MapStat).first()
        self.assertEqual(result.lat, 12345)
        self.assertEqual(result.lon, -23456)
        self.assertEqual(result.time, today)


class TestScore(DBTestCase):

    def test_fields(self):
        utcday = util.utcnow().date()
        self.session.add(Score(
            key=ScoreKey.location, userid=3, time=utcday, value=15))
        self.session.flush()

        result = self.session.query(Score).first()
        self.assertEqual(result.key, ScoreKey.location)
        self.assertEqual(result.userid, 3)
        self.assertEqual(result.time, utcday)
        self.assertEqual(result.value, 15)

    def test_enum(self):
        utcday = util.utcnow().date()
        self.session.add(Score(
            key=ScoreKey.location, userid=3, time=utcday, value=13))
        self.session.flush()

        result = self.session.query(Score).first()
        self.assertEqual(result.key, ScoreKey.location)
        self.assertEqual(int(result.key), 0)
        self.assertEqual(result.key.name, 'location')


class TestStat(DBTestCase):

    def test_fields(self):
        utcday = util.utcnow().date()
        self.session.add(Stat(key=StatKey.cell, time=utcday, value=13))
        self.session.flush()

        result = self.session.query(Stat).first()
        self.assertEqual(result.key, StatKey.cell)
        self.assertEqual(result.time, utcday)
        self.assertEqual(result.value, 13)

    def test_enum(self):
        utcday = util.utcnow().date()
        self.session.add(Stat(key=StatKey.cell, time=utcday, value=13))
        self.session.flush()

        result = self.session.query(Stat).first()
        self.assertEqual(result.key, StatKey.cell)
        self.assertEqual(int(result.key), 1)
        self.assertEqual(result.key.name, 'cell')


class TestUser(DBTestCase):

    def test_fields(self):
        nickname = u'World Tr\xc3\xa4veler'
        email = u'world_tr\xc3\xa4veler@email.com'
        self.session.add(User(nickname=nickname, email=email))
        self.session.flush()

        result = self.session.query(User).first()
        self.assertEqual(result.nickname, nickname)
        self.assertEqual(result.email, email)
