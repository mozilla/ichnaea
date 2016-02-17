from datetime import datetime

from pytz import UTC

from ichnaea.exceptions import GZIPDecodeError
from ichnaea.tests.base import TestCase
from ichnaea import util


class TestUtil(TestCase):

    gzip_foo = (b'\x1f\x8b\x08\x00\xed\x7f\x9aU\x02\xffK'
                b'\xcb\xcf\x07\x00!es\x8c\x03\x00\x00\x00')

    def test_utcnow(self):
        now = util.utcnow()
        self.assertTrue(isinstance(now, datetime))
        self.assertEqual(now.tzinfo, UTC)

    def test_encode_gzip(self):
        data = util.encode_gzip(u'foo')
        self.assertEqual(data[:4], self.gzip_foo[:4])
        self.assertEqual(data[-13:], self.gzip_foo[-13:])

    def test_encode_gzip_bytes(self):
        data = util.encode_gzip(b'foo')
        self.assertEqual(data[:4], self.gzip_foo[:4])
        self.assertEqual(data[-13:], self.gzip_foo[-13:])

    def test_decode_gzip(self):
        data = util.decode_gzip(self.gzip_foo)
        self.assertEqual(data, u'foo')

    def test_roundtrip_gzip(self):
        data = util.decode_gzip(util.encode_gzip(b'foo'))
        self.assertEqual(data, u'foo')

    def test_decode_gzip_error(self):
        self.assertRaises(GZIPDecodeError, util.decode_gzip, self.gzip_foo[:1])
        self.assertRaises(GZIPDecodeError, util.decode_gzip, self.gzip_foo[:5])
