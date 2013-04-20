import decimal

import simplejson as json


def dump_decimal_json(value):
    with decimal.localcontext() as ctx:
        ctx.prec = 6
        return json.dumps(value, use_decimal=True)


class DecimalJSON(object):

    def __call__(self, info):
        def _render(value, system):
            request = system.get('request')
            if request is not None:
                request.response.content_type = 'application/json'
            return dump_decimal_json(value)
        return _render
