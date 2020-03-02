from datetime import datetime

import pytest
from pytz import UTC

from ichnaea.exceptions import GZIPDecodeError
from ichnaea import util


class TestUtil(object):

    gzip_foo = (
        b"\x1f\x8b\x08\x00\xed\x7f\x9aU\x00\xffK"
        b"\xcb\xcf\x07\x00!es\x8c\x03\x00\x00\x00"
    )

    def test_utcnow(self):
        now = util.utcnow()
        assert isinstance(now, datetime)
        assert now.tzinfo == UTC

    def test_encode_gzip(self):
        data = util.encode_gzip(b"foo")
        # Test around the 4-byte timestamp
        assert data[:4] == self.gzip_foo[:4]
        assert data[8:] == self.gzip_foo[8:]

    def test_decode_gzip(self):
        data = util.decode_gzip(self.gzip_foo)
        assert data == b"foo"

    def test_roundtrip_gzip(self):
        data = util.decode_gzip(util.encode_gzip(b"foo"))
        assert data == b"foo"

    def test_decode_gzip_error(self):
        with pytest.raises(GZIPDecodeError):
            util.decode_gzip(self.gzip_foo[:1])
        with pytest.raises(GZIPDecodeError):
            util.decode_gzip(self.gzip_foo[:5])
