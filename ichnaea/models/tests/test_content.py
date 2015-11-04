from ichnaea.models.content import (
    decode_datamap_grid,
    encode_datamap_grid,
    DataMap,
    MapStat,
    RegionStat,
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
            decode_datamap_grid(b'\x00\x00\x00\x00\x00\x00\x00\x00'),
            (-90000, -180000))
        self.assertEqual(
            decode_datamap_grid(b'AAAAAAAAAAA=', codec='base64'),
            (-90000, -180000))

        self.assertEqual(
            decode_datamap_grid(b'\x00\x01_\x90\x00\x02\xbf '),
            (0, 0))
        self.assertEqual(
            decode_datamap_grid(b'AAFfkAACvyA=', codec='base64'),
            (0, 0))

        self.assertEqual(
            decode_datamap_grid(b'\x00\x02\xbf \x00\x05~@'),
            (90000, 180000))
        self.assertEqual(
            decode_datamap_grid(b'\x00\x02\xbf \x00\x05~@', scale=True),
            (90.0, 180.0))
        self.assertEqual(
            decode_datamap_grid(b'AAK/IAAFfkA=', codec='base64'),
            (90000, 180000))
        self.assertEqual(
            decode_datamap_grid(b'AAK/IAAFfkA=', scale=True, codec='base64'),
            (90.0, 180.0))

    def test_encode_datamap_grid(self):
        self.assertEqual(encode_datamap_grid(-90000, -180000),
                         b'\x00\x00\x00\x00\x00\x00\x00\x00')
        self.assertEqual(encode_datamap_grid(-90000, -180000, codec='base64'),
                         b'AAAAAAAAAAA=')

        self.assertEqual(encode_datamap_grid(0, 0),
                         b'\x00\x01_\x90\x00\x02\xbf ')
        self.assertEqual(encode_datamap_grid(0, 0, codec='base64'),
                         b'AAFfkAACvyA=')

        self.assertEqual(encode_datamap_grid(90.0, 180.0, scale=True),
                         b'\x00\x02\xbf \x00\x05~@')
        self.assertEqual(encode_datamap_grid(90000, 180000),
                         b'\x00\x02\xbf \x00\x05~@')
        self.assertEqual(encode_datamap_grid(90000, 180000, codec='base64'),
                         b'AAK/IAAFfkA=')


class TestDataMap(DBTestCase):

    def test_fields(self):
        today = util.utcnow().date()
        lat = 12345
        lon = -23456
        model = DataMap.shard_model(lat, lon)
        self.session.add(model(grid=(lat, lon), created=today, modified=today))
        self.session.flush()
        result = self.session.query(model).first()
        self.assertEqual(result.grid, (lat, lon))
        self.assertEqual(result.created, today)
        self.assertEqual(result.modified, today)

    def test_scale(self):
        self.assertEqual(DataMap.scale(-1.12345678, 2.23456789),
                         (-1123, 2235))

    def test_shard_id(self):
        self.assertEqual(DataMap.shard_id(None, None), None)
        self.assertEqual(DataMap.shard_id(85000, 180000), 'ne')
        self.assertEqual(DataMap.shard_id(36000, 5000), 'ne')
        self.assertEqual(DataMap.shard_id(35999, 5000), 'se')
        self.assertEqual(DataMap.shard_id(-85000, 180000), 'se')
        self.assertEqual(DataMap.shard_id(85000, -180000), 'nw')
        self.assertEqual(DataMap.shard_id(36000, 4999), 'nw')
        self.assertEqual(DataMap.shard_id(35999, 4999), 'sw')
        self.assertEqual(DataMap.shard_id(-85000, -180000), 'sw')

    def test_grid_bytes(self):
        lat = 12000
        lon = 34000
        grid = encode_datamap_grid(lat, lon)
        model = DataMap.shard_model(lat, lon)
        self.session.add(model(grid=grid))
        self.session.flush()
        result = self.session.query(model).first()
        self.assertEqual(result.grid, (lat, lon))

    def test_grid_none(self):
        self.session.add(DataMap.shard_model(0, 0)(grid=None))
        with self.assertRaises(Exception):
            self.session.flush()

    def test_grid_length(self):
        self.session.add(DataMap.shard_model(0, 9)(grid=b'\x00' * 9))
        with self.assertRaises(Exception):
            self.session.flush()

    def test_grid_list(self):
        lat = 1000
        lon = -2000
        self.session.add(DataMap.shard_model(lat, lon)(grid=[lat, lon]))
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


class TestRegionStat(DBTestCase):

    def test_fields(self):
        self.session.add(RegionStat(
            region='GB', gsm=1, wcdma=2, lte=3, wifi=4))
        self.session.flush()

        result = self.session.query(RegionStat).first()
        self.assertEqual(result.region, 'GB')
        self.assertEqual(result.gsm, 1)
        self.assertEqual(result.wcdma, 2)
        self.assertEqual(result.lte, 3)
        self.assertEqual(result.wifi, 4)


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
