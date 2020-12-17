from datetime import datetime

import pytest
from zoneinfo import ZoneInfo

from ichnaea.exceptions import GZIPDecodeError
from ichnaea import util


class TestUtil(object):

    gzip_foo = (b'\x1f\x8b\x08\x00\xed\x7f\x9aU\x02\xffK'
                b'\xcb\xcf\x07\x00!es\x8c\x03\x00\x00\x00')

    def test_utcnow(self):
        now = util.utcnow()
        assert isinstance(now, datetime)
        assert now.tzinfo == UTC

    def test_encode_gzip(self):
        data = util.encode_gzip(u'foo')
        assert data[:4] == self.gzip_foo[:4]
        assert data[-13:] == self.gzip_foo[-13:]

    def test_encode_gzip_bytes(self):
        data = util.encode_gzip(b'foo')
        assert data[:4] == self.gzip_foo[:4]
        assert data[-13:] == self.gzip_foo[-13:]

    def test_decode_gzip(self):
        data = util.decode_gzip(self.gzip_foo)
        assert data == u'foo'

    def test_roundtrip_gzip(self):
        data = util.decode_gzip(util.encode_gzip(b'foo'))
        assert data == u'foo'

    def test_no_encoding(self):
        data = util.encode_gzip(b'\x00ab', encoding=None)
        assert isinstance(data, bytes)
        result = util.decode_gzip(data, encoding=None)
        assert isinstance(result, bytes)
        assert result == b'\x00ab'

    def test_decode_gzip_error(self):
        with pytest.raises(GZIPDecodeError):
            util.decode_gzip(self.gzip_foo[:1])
        with pytest.raises(GZIPDecodeError):
            util.decode_gzip(self.gzip_foo[:5])
