import pytest

from ichnaea.models.content import (
    decode_datamap_grid,
    encode_datamap_grid,
    DataMap,
    RegionStat,
    Stat,
    StatKey,
)
from ichnaea.tests.base import DBTestCase
from ichnaea import util


class TestDataMapCodec(object):

    def test_decode_datamap_grid(self):
        assert (decode_datamap_grid(
                b'\x00\x00\x00\x00\x00\x00\x00\x00') == (-90000, -180000))
        assert (decode_datamap_grid(
                b'AAAAAAAAAAA=', codec='base64') == (-90000, -180000))

        assert (decode_datamap_grid(b'\x00\x01_\x90\x00\x02\xbf ') == (0, 0))
        assert (decode_datamap_grid(b'AAFfkAACvyA=', codec='base64') == (0, 0))

        assert (decode_datamap_grid(
                b'\x00\x02\xbf \x00\x05~@') == (90000, 180000))
        assert (decode_datamap_grid(
                b'\x00\x02\xbf \x00\x05~@', scale=True) == (90.0, 180.0))
        assert (decode_datamap_grid(
                b'AAK/IAAFfkA=', codec='base64') == (90000, 180000))
        assert (decode_datamap_grid(
                b'AAK/IAAFfkA=', scale=True, codec='base64') == (90.0, 180.0))

    def test_encode_datamap_grid(self):
        assert (encode_datamap_grid(
                -90000, -180000) == b'\x00\x00\x00\x00\x00\x00\x00\x00')
        assert (encode_datamap_grid(
                -90000, -180000, codec='base64') == b'AAAAAAAAAAA=')

        assert (encode_datamap_grid(0, 0) == b'\x00\x01_\x90\x00\x02\xbf ')
        assert (encode_datamap_grid(0, 0, codec='base64') == b'AAFfkAACvyA=')

        assert (encode_datamap_grid(
                90.0, 180.0, scale=True) == b'\x00\x02\xbf \x00\x05~@')
        assert (encode_datamap_grid(
                90000, 180000) == b'\x00\x02\xbf \x00\x05~@')
        assert (encode_datamap_grid(
                90000, 180000, codec='base64') == b'AAK/IAAFfkA=')


class TestDataMap(DBTestCase):

    def test_fields(self):
        today = util.utcnow().date()
        lat = 12345
        lon = -23456
        model = DataMap.shard_model(lat, lon)
        self.session.add(model(grid=(lat, lon), created=today, modified=today))
        self.session.flush()
        result = self.session.query(model).first()
        assert result.grid == (lat, lon)
        assert result.created == today
        assert result.modified == today

    def test_scale(self):
        assert DataMap.scale(-1.12345678, 2.23456789) == (-1123, 2235)

    def test_shard_id(self):
        assert DataMap.shard_id(None, None) is None
        assert DataMap.shard_id(85000, 180000) == 'ne'
        assert DataMap.shard_id(36000, 5000) == 'ne'
        assert DataMap.shard_id(35999, 5000) == 'se'
        assert DataMap.shard_id(-85000, 180000) == 'se'
        assert DataMap.shard_id(85000, -180000) == 'nw'
        assert DataMap.shard_id(36000, 4999) == 'nw'
        assert DataMap.shard_id(35999, 4999) == 'sw'
        assert DataMap.shard_id(-85000, -180000) == 'sw'

    def test_grid_bytes(self):
        lat = 12000
        lon = 34000
        grid = encode_datamap_grid(lat, lon)
        model = DataMap.shard_model(lat, lon)
        self.session.add(model(grid=grid))
        self.session.flush()
        result = self.session.query(model).first()
        assert result.grid == (lat, lon)

    def test_grid_none(self):
        self.session.add(DataMap.shard_model(0, 0)(grid=None))
        with pytest.raises(Exception):
            self.session.flush()

    def test_grid_length(self):
        self.session.add(DataMap.shard_model(0, 9)(grid=b'\x00' * 9))
        with pytest.raises(Exception):
            self.session.flush()

    def test_grid_list(self):
        lat = 1000
        lon = -2000
        self.session.add(DataMap.shard_model(lat, lon)(grid=[lat, lon]))
        with pytest.raises(Exception):
            self.session.flush()


class TestRegionStat(DBTestCase):

    def test_fields(self):
        self.session.add(RegionStat(
            region='GB', gsm=1, wcdma=2, lte=3, blue=4, wifi=5))
        self.session.flush()

        result = self.session.query(RegionStat).first()
        assert result.region == 'GB'
        assert result.gsm == 1
        assert result.wcdma == 2
        assert result.lte == 3
        assert result.blue == 4
        assert result.wifi == 5


class TestStat(DBTestCase):

    def test_fields(self):
        utcday = util.utcnow().date()
        self.session.add(Stat(key=StatKey.cell, time=utcday, value=13))
        self.session.flush()

        result = self.session.query(Stat).first()
        assert result.key == StatKey.cell
        assert result.time == utcday
        assert result.value == 13

    def test_enum(self):
        utcday = util.utcnow().date()
        self.session.add(Stat(key=StatKey.cell, time=utcday, value=13))
        self.session.flush()

        result = self.session.query(Stat).first()
        assert result.key == StatKey.cell
        assert int(result.key) == 1
        assert result.key.name == 'cell'
