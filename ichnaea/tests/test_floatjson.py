from ichnaea.floatjson import (
    float_dumps,
    FloatJSONRenderer,
)
from ichnaea.tests.base import TestCase


class TestFloatJSONRenderer(TestCase):

    def setUp(self):
        super(TestFloatJSONRenderer, self).setUp()
        self.render = FloatJSONRenderer()(None)

    def test_basic(self):
        self.assertEqual(self.render({'a': 1}, {}), '{"a": 1}')

    def test_high_precision(self):
        self.assertEqual(self.render({'accuracy': 12.345678}, {}),
                         '{"accuracy": 12.345678}')

    def test_low_precision(self):
        self.assertEqual(self.render({'accuracy': 12.34}, {}),
                         '{"accuracy": 12.34}')

    def test_rounded(self):
        expect = '{"z": 1.1}'
        self.assertEqual(self.render({'z': 3.3 / 3}, {}), expect)

    def test_error(self):
        self.assertRaises(TypeError, float_dumps, object())
