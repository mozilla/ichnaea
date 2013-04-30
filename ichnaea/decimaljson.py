from decimal import Decimal
from decimal import localcontext

import simplejson as json

FACTOR = Decimal(10000000)
EXPONENT_STR = '1.0000000'
EXPONENT = Decimal(EXPONENT_STR)
PRECISION = 7


def dumps(value):
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return json.dumps(value, use_decimal=True)


def loads(value):
    with localcontext() as ctx:
        ctx.prec = PRECISION
        return json.loads(value, use_decimal=True)


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
