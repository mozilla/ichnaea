import pytest

from ichnaea.floatjson import (
    float_dumps,
    FloatJSONRenderer,
)


class TestFloatJSONRenderer(object):

    @property
    def render(self):
        return FloatJSONRenderer()(None)

    def test_basic(self):
        assert self.render({'a': 1}, {}) == '{"a": 1}'

    def test_high_precision(self):
        assert (self.render({'accuracy': 12.345678}, {}) ==
                '{"accuracy": 12.345678}')

    def test_low_precision(self):
        assert (self.render({'accuracy': 12.34}, {}) ==
                '{"accuracy": 12.34}')

    def test_error(self):
        with pytest.raises(TypeError):
            float_dumps(object())
