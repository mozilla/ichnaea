import sys
import simplejson as json
from ichnaea.models import encode_datetime
from contextlib import contextmanager


@contextmanager
def custom_floating_point_repr(value):

    if isinstance(value, dict) \
       and 'accuracy' in value \
       and sys.version_info < (2, 7):

        # Temporarily monkey-patch simplejson to emit floats using str()
        # rather than repr() when running under python2.6 or earlier and
        # writing out a dict that has an 'accuracy' key.
        #
        # We want to do this because 2.6 doesn't round floating point values
        # very nicely:
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
        #
        # But we want to be careful to only do this temporarily and in the
        # context of rendering a response for a search or geolocate API
        # customer, which we guess at by looking for an 'accuracy' key in
        # the value.

        import simplejson.encoder as enc

        # This is the replacement repr function we're going to inject.
        def frepr(ob):
            if isinstance(ob, float):
                return str(ob)
            else:
                return repr(ob)

        # First disable the C encoder, causing the module to use
        # its own python fallbacks.
        saved_c_make_encoder = enc.c_make_encoder
        enc.c_make_encoder = None

        # Then inject our repr function into the python encoder.
        saved_float_repr = enc.FLOAT_REPR
        enc.FLOAT_REPR = frepr

        try:
            yield
        finally:
            # Restore saved values
            enc.c_make_encoder = saved_c_make_encoder
            enc.FLOAT_REPR = saved_float_repr

    else:
        # Any other circumstance (rendering non-'accuracy'-containing
        # responses, or rendering on >= python2.7) we do not patch.
        yield


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
            with custom_floating_point_repr(value):
                return dumps(value)
        return _render
