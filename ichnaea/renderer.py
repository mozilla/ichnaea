import decimal

import simplejson as json


class DecimalJSON(object):

    def __call__(self, info):
        def _render(value, system):
            with decimal.localcontext() as ctx:
                ctx.prec = 6
                ret = json.dumps(value, use_decimal=True)
            request = system.get('request')
            if request is not None:
                request.response.content_type = 'application/json'
            return ret
        return _render
