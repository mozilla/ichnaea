from collections import namedtuple

from sqlalchemy import (
    Column,
    Index,
    String,
    UniqueConstraint,
)

from ichnaea.models.base import (
    _Model,
    BigIdMixin,
)
from ichnaea.models.station import (
    StationMixin,
    StationBlacklistMixin,
)
from ichnaea import util


WifiKey = namedtuple('WifiKey', 'key')


def to_wifikey(obj):
    if isinstance(obj, dict):  # pragma: no cover
        return WifiKey(key=obj['key'])
    elif isinstance(obj, basestring):  # pragma: no cover
        return WifiKey(key=obj)
    else:
        return WifiKey(key=obj.key)


def join_wifikey(model, k):
    return (model.key == k.key,)


class WifiKeyMixin(object):

    key = Column(String(12))


class WifiMixin(BigIdMixin, WifiKeyMixin):
    pass


class Wifi(WifiMixin, StationMixin, _Model):
    __tablename__ = 'wifi'

    _indices = (
        UniqueConstraint('key', name='wifi_key_unique'),
        Index('wifi_created_idx', 'created'),
        Index('wifi_new_measures_idx', 'new_measures'),
        Index('wifi_total_measures_idx', 'total_measures'),
    )

    def __init__(self, *args, **kw):
        if 'created' not in kw:
            kw['created'] = util.utcnow()
        if 'modified' not in kw:
            kw['modified'] = util.utcnow()
        if 'new_measures' not in kw:
            kw['new_measures'] = 0
        if 'total_measures' not in kw:
            kw['total_measures'] = 0
        super(Wifi, self).__init__(*args, **kw)


class WifiBlacklist(WifiMixin, StationBlacklistMixin, _Model):
    __tablename__ = 'wifi_blacklist'

    _indices = (
        UniqueConstraint('key', name='wifi_blacklist_key_unique'),
    )

    def __init__(self, *args, **kw):
        if 'time' not in kw:
            kw['time'] = util.utcnow()
        if 'count' not in kw:
            kw['count'] = 1
        super(WifiBlacklist, self).__init__(*args, **kw)
