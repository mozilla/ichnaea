from decimal import Decimal
from decimal import localcontext
from ichnaea.models import DEGREE_DECIMAL_PLACES, encode_datetime
import simplejson as json

FACTOR = Decimal(10 ** DEGREE_DECIMAL_PLACES)
EXPONENT_STR = '1.' + ('0' * DEGREE_DECIMAL_PLACES)
EXPONENT = Decimal(EXPONENT_STR)
PRECISION = DEGREE_DECIMAL_PLACES


def dumps(value):
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return json.dumps(value, use_decimal=True, default=encode_datetime)


def loads(value, encoding="utf-8"):
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return json.loads(value, use_decimal=True, encoding=encoding)


def quantize(value):
    return (Decimal(value) / FACTOR).quantize(EXPONENT)


def to_precise_int(value):
    if isinstance(value, str):
        value = Decimal(value)
    return int(value * FACTOR)


class Renderer(object):

    def __call__(self, info):
        def _render(value, system):
            request = system.get('request')
            if request is not None:
                request.response.content_type = 'application/json'
            return dumps(value)
        return _render
