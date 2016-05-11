from ichnaea.models.mac import (
    channel_frequency,
    decode_mac,
    encode_mac,
)


class TestChannelFrequency(object):

    def compare(self, channel, frequency, channel_expect, frequency_expect):
        new_channel, new_frequency = channel_frequency(
            channel=channel, frequency=frequency)
        assert new_channel == channel_expect
        assert new_frequency == frequency_expect

    def test_channel(self):
        self.compare(1, None, 1, 2412)
        self.compare(13, None, 13, 2472)
        self.compare(14, None, 14, 2484)
        self.compare(15, None, 15, 5075)
        self.compare(36, None, 36, 5180)
        self.compare(185, None, 185, 5925)
        self.compare(186, None, 186, 4930)
        self.compare(199, None, 199, 4995)

    def test_channel_frequency(self):
        self.compare(None, None, None, None)
        self.compare(4, None, 4, 2427)
        self.compare(None, 2412, 1, 2412)
        self.compare(3, 2412, 3, 2412)

    def test_frequency(self):
        self.compare(None, 2411, None, 2411)
        self.compare(None, 2412, 1, 2412)
        self.compare(None, 2472, 13, 2472)
        self.compare(None, 2473, None, 2473)
        self.compare(None, 2484, 14, 2484)
        self.compare(None, 4910, None, 4910)
        self.compare(None, 4915, 183, 4915)
        self.compare(None, 4995, 199, 4995)
        self.compare(None, 5000, None, 5000)
        self.compare(None, 5074, None, 5074)
        self.compare(None, 5075, 15, 5075)
        self.compare(None, 5180, 36, 5180)
        self.compare(None, 5925, 185, 5925)
        self.compare(None, 5930, None, 5930)


class TestMacCodec(object):

    def test_decode(self):
        assert decode_mac(b'\xab\xcd\xed\x124V') == 'abcded123456'
        assert decode_mac(b'q83tEjRW', codec='base64') == 'abcded123456'

    def test_encode(self):
        assert encode_mac('abcded123456') == b'\xab\xcd\xed\x124V'
        assert encode_mac('abcded123456', codec='base64') == b'q83tEjRW'

    def test_max(self):
        assert encode_mac('ffffffffffff') == b'\xff\xff\xff\xff\xff\xff'
        assert encode_mac('ffffffffffff', codec='base64') == b'////////'

    def test_min(self):
        assert encode_mac('000000000000') == b'\x00\x00\x00\x00\x00\x00'
        assert encode_mac('000000000000', codec='base64') == b'AAAAAAAA'
