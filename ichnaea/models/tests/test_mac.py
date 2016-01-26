from ichnaea.models.mac import (
    decode_mac,
    encode_mac,
)
from ichnaea.tests.base import (
    TestCase,
)


class TestMacCodec(TestCase):

    def test_decode(self):
        value = decode_mac(b'\xab\xcd\xed\x124V')
        self.assertEqual(value, 'abcded123456')

        value = decode_mac(b'q83tEjRW', codec='base64')
        self.assertEqual(value, 'abcded123456')

    def test_encode(self):
        value = encode_mac('abcded123456')
        self.assertEqual(len(value), 6)
        self.assertEqual(value, b'\xab\xcd\xed\x124V')

        value = encode_mac('abcded123456', codec='base64')
        self.assertEqual(value, b'q83tEjRW')

    def test_max(self):
        value = encode_mac('ffffffffffff')
        self.assertEqual(len(value), 6)
        self.assertEqual(value, b'\xff\xff\xff\xff\xff\xff')

        value = encode_mac('ffffffffffff', codec='base64')
        self.assertEqual(value, b'////////')

    def test_min(self):
        value = encode_mac('000000000000')
        self.assertEqual(len(value), 6)
        self.assertEqual(value, b'\x00\x00\x00\x00\x00\x00')

        value = encode_mac('000000000000', codec='base64')
        self.assertEqual(value, b'AAAAAAAA')
