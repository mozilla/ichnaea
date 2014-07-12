import simplejson as json
from ichnaea.models import (encode_datetime, DEGREE_DECIMAL_PLACES)


def custom_iterencode(value):
    from simplejson.encoder import (
        JSONEncoder,
        _make_iterencode,
        FLOAT_REPR,
        PosInf,
        encode_basestring
    )
    from decimal import Decimal

    j = JSONEncoder()

    def floatstr(o, allow_nan=j.allow_nan, ignore_nan=j.ignore_nan,
                 _repr=FLOAT_REPR, _inf=PosInf, _neginf=-PosInf):
        if o != o:
            text = 'NaN'
        elif o == _inf:
            text = 'Infinity'
        elif o == _neginf:
            text = '-Infinity'
        else:
            return str(round(o, DEGREE_DECIMAL_PLACES))
        if ignore_nan:
            text = 'null'
        elif not allow_nan:
            raise ValueError(
                "Out of range float values are not JSON compliant: " +
                repr(o))

        return text

    markers = {}
    _encoder = encode_basestring
    _one_shot = False
    _iterencode = _make_iterencode(
        markers, j.default, _encoder, j.indent, floatstr,
        j.key_separator, j.item_separator, j.sort_keys,
        j.skipkeys, _one_shot, j.use_decimal,
        j.namedtuple_as_object, j.tuple_as_array,
        j.bigint_as_string, j.item_sort_key,
        j.encoding, j.for_json,
        Decimal=Decimal)

    return _iterencode(value, 0)


def dumps(value):

    if isinstance(value, dict) \
       and 'accuracy' in value: \

        # Use a custom variant of simplejson to emit floats using str()
        # rather than repr(). Initially we did this only when running under
        # python2.6 or earlier and writing out a dict that has an
        # 'accuracy' key, but now we do it for any dict with an 'accuracy'
        # key.
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
        # Python 2.7 has fixed _that_ bug but it still has a tendency towards
        # producing curious rounding artifacts:
        #
        # In python 2.7:
        #
        # >>> repr(3.3/3)
        # '1.0999999999999999'
        # >>> repr(3.03/3)
        # '1.01'
        # >>> repr(3.003/3)
        # '1.0010000000000001'
        # >>> repr(3.0003/3)
        # '1.0001'
        # >>> repr(3.00003/3)
        # '1.00001'
        #
        # This behavior is preserved in python3, and made "more uniform" merely
        # by causing str() to do the same thing. So we explicitly round in the
        # custom_iterencode routine.

        return u''.join(custom_iterencode(value))

    else:

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
