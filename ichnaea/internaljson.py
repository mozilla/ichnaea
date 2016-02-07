"""
Functionality around an internal JSON derivative format.
This format is used inside the Celery/Kombu queues but is not suitable
for any external communication with third party systems.
"""
from calendar import timegm
from datetime import date, datetime

from pytz import UTC
import simplejson

from ichnaea.models.base import JSONMixin


def internal_default(obj):
    if isinstance(obj, datetime):
        if obj.utcoffset() is not None:
            obj = obj - obj.utcoffset()
        millis = int(timegm(obj.timetuple()) * 1000 + obj.microsecond / 1000)
        return {'__datetime__': millis}
    elif isinstance(obj, date):
        return {'__date__': [obj.year, obj.month, obj.day]}
    elif isinstance(obj, JSONMixin):
        return obj._to_json()
    raise TypeError('%r is not JSON serializable' % obj)  # pragma: no cover


def internal_object_hook(dct):
    if '__datetime__' in dct:
        secs = float(dct['__datetime__']) / 1000.0
        return datetime.utcfromtimestamp(secs).replace(tzinfo=UTC)
    elif '__date__' in dct:
        return date(*dct['__date__'])
    elif '__class__' in dct:
        return JSONMixin._from_json(dct)
    return dct


def internal_dumps(value):
    """
    Dump an object into a special internal JSON format with support
    for roundtripping date and datetime classes
    """
    return simplejson.dumps(value, default=internal_default,
                            namedtuple_as_object=True, separators=(',', ':'))


def internal_loads(value):
    """
    Load a bytes object in internal JSON format.
    """
    return simplejson.loads(value, object_hook=internal_object_hook)
