from calendar import timegm
from datetime import date, datetime
from uuid import UUID

from pyramid.path import DottedNameResolver
from pytz import UTC
import simplejson as json

from ichnaea.constants import DEGREE_DECIMAL_PLACES
from ichnaea.models.base import HashKey

RESOLVER = DottedNameResolver('ichnaea')


def encode_datetime(obj):
    if isinstance(obj, datetime):
        return obj.strftime('%Y-%m-%dT%H:%M:%S.%f')
    elif isinstance(obj, date):
        return obj.strftime('%Y-%m-%d')
    raise TypeError(repr(obj) + " is not JSON serializable")


def custom_iterencode(value):
    from simplejson.encoder import (
        _make_iterencode,
        encode_basestring,
        FLOAT_REPR,
        JSONEncoder,
        PosInf,
    )

    j = JSONEncoder()

    def floatstr(o, allow_nan=j.allow_nan, ignore_nan=j.ignore_nan,
                 _repr=FLOAT_REPR, _inf=PosInf,
                 _neginf=-PosInf):  # pragma: no cover
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
        j.int_as_string_bitcount, j.item_sort_key,
        j.encoding, j.for_json,
    )

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


def kombu_default(obj):
    if isinstance(obj, datetime):
        if obj.utcoffset() is not None:
            obj = obj - obj.utcoffset()
        millis = int(timegm(obj.timetuple()) * 1000 + obj.microsecond / 1000)
        return {'__datetime__': millis}
    elif isinstance(obj, date):
        return {'__date__': [obj.year, obj.month, obj.day]}
    elif isinstance(obj, UUID):
        return {'__uuid__': obj.hex}
    elif isinstance(obj, HashKey):
        return {'__hashkey__': {
            'name': obj._dottedname,
            'value': obj.__dict__,
        }}
    raise TypeError("%r is not JSON serializable" % obj)  # pragma: no cover


def kombu_object_hook(dct):
    if '__datetime__' in dct:
        secs = float(dct['__datetime__']) / 1000.0
        return datetime.utcfromtimestamp(secs).replace(tzinfo=UTC)
    elif '__date__' in dct:
        return date(*dct['__date__'])
    elif '__uuid__' in dct:
        return UUID(hex=dct['__uuid__'])
    elif '__hashkey__' in dct:
        hashkey = dct['__hashkey__']
        klass = RESOLVER.resolve(hashkey['name'])
        return klass(**hashkey['value'])
    return dct


def kombu_dumps(value):
    return json.dumps(value, default=kombu_default,
                      namedtuple_as_object=True, separators=(',', ':'))


def kombu_loads(value):
    return json.loads(value, object_hook=kombu_object_hook)
