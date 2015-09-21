"""
A JSON dumps function and Renderer which use a prettier float representation.
This avoids seeing `1.1` as `'1.1000000000000001'` inside the returned JSON.
"""
import sys

import simplejson

from ichnaea.constants import DEGREE_DECIMAL_PLACES


def custom_iterencode(value):  # pragma: no cover
    from simplejson.encoder import (
        _make_iterencode,
        encode_basestring,
        FLOAT_REPR,
        JSONEncoder,
        PosInf,
    )

    jenc = JSONEncoder()

    def floatstr(o, allow_nan=jenc.allow_nan, ignore_nan=jenc.ignore_nan,
                 _repr=FLOAT_REPR, _inf=PosInf,
                 _neginf=-PosInf):  # pragma: no cover
        if o != o:
            text = 'NaN'
        elif o == _inf:
            text = 'Infinity'
        elif o == _neginf:
            text = '-Infinity'
        else:
            if type(o) != float:
                # See #118, do not trust custom str/repr
                o = float(o)
            # use str(round()) instead of repr()
            return str(round(o, DEGREE_DECIMAL_PLACES))

        if ignore_nan:
            text = 'null'
        elif not allow_nan:
            raise ValueError(
                'Out of range float values are not JSON compliant: ' +
                repr(o))

        return text

    markers = {}
    _encoder = encode_basestring
    _one_shot = False
    _iterencode = _make_iterencode(
        markers, jenc.default, _encoder, jenc.indent, floatstr,
        jenc.key_separator, jenc.item_separator, jenc.sort_keys,
        jenc.skipkeys, _one_shot, jenc.use_decimal,
        jenc.namedtuple_as_object, jenc.tuple_as_array,
        jenc.int_as_string_bitcount, jenc.item_sort_key,
        jenc.encoding, jenc.for_json, jenc.iterable_as_array,
    )

    return _iterencode(value, 0)


if sys.version_info < (2, 7):  # pragma: no cover
    def float_dumps(value):
        return u''.join(custom_iterencode(value))
else:  # pragma: no cover
    float_dumps = simplejson.dumps


class FloatJSONRenderer(object):
    """A JSON renderer providing a nicer float representation."""

    def __call__(self, info):
        def _render(value, system):
            request = system.get('request')
            if request is not None:
                request.response.content_type = 'application/json'
            return float_dumps(value)
        return _render
