import simplejson

from ichnaea.models.base import JSONMixin


def internal_default(obj):
    if isinstance(obj, JSONMixin):
        # BBB
        return obj._to_json()
    raise TypeError('%r is not JSON serializable' % obj)  # pragma: no cover


def internal_object_hook(dct):
    if '__class__' in dct:
        # BBB
        return JSONMixin._from_json(dct)
    return dct


def internal_dumps(value):
    return simplejson.dumps(value, default=internal_default,
                            separators=(',', ':'))


def internal_loads(value):
    return simplejson.loads(value, object_hook=internal_object_hook)
