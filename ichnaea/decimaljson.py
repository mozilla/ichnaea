from decimal import Decimal
from decimal import localcontext

import simplejson as json

MILLION = Decimal(1000000)
ONE_SIX_ZEROS = Decimal('1.000000')


def dumps(value):
    with localcontext() as ctx:
        ctx.prec = 6
        return json.dumps(value, use_decimal=True)


def loads(value):
    with localcontext() as ctx:
        ctx.prec = 6
        return json.loads(value, use_decimal=True)


def quantize(value):
    return (Decimal(value) / MILLION).quantize(ONE_SIX_ZEROS)


class Renderer(object):

    def __call__(self, info):
        def _render(value, system):
            request = system.get('request')
            if request is not None:
                request.response.content_type = 'application/json'
            return dumps(value)
        return _render
