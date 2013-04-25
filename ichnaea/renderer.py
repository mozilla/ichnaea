from decimal import Decimal
from decimal import localcontext

import simplejson as json

MILLION = Decimal(1000000)


def dump_decimal_json(value):
    with localcontext() as ctx:
        ctx.prec = 6
        return json.dumps(value, use_decimal=True)


def loads_decimal_json(value):
    with localcontext() as ctx:
        ctx.prec = 6
        return json.loads(value, use_decimal=True)


def quantize(value):
    return (Decimal(value) / MILLION).quantize(Decimal('1.000000'))


class DecimalJSON(object):

    def __call__(self, info):
        def _render(value, system):
            request = system.get('request')
            if request is not None:
                request.response.content_type = 'application/json'
            return dump_decimal_json(value)
        return _render
