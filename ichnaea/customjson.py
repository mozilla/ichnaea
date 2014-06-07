import sys
import simplejson as json
from ichnaea.models import encode_datetime


def dumps(value):
    return json.dumps(value, default=encode_datetime)


def loads(value, encoding="utf-8"):
    return json.loads(value, encoding=encoding)


class Renderer(object):

    def __call__(self, info):
        def _render(value, system):
            request = system.get('request')
            if request is not None:
                request.response.content_type = 'application/json'
            return dumps(value)
        return _render


if sys.version_info < (2, 7):

    # monkey-patch simplejson to emit floats using str() rather than repr()
    # when running under python2.6 or earlier. Because 2.6 doesn't round the
    # result pleasantly.
    #
    # In python2.7:
    #
    # >>> repr(1.1)
    # '1.1'
    #
    # In python2.6:
    #
    # >>> repr(1.1)
    # '1.1000000000000001'

    import simplejson.encoder as enc

    # This is the replacement repr function we're going to inject.
    def frepr(ob):
        if isinstance(ob, float):
            return str(ob)
        else:
            return repr(ob)

    # First disable the C encoder, causing the module to use
    # its own python fallbacks.
    enc.c_make_encoder = None

    # Then inject our repr function into the python encoder.
    enc.FLOAT_REPR = frepr
