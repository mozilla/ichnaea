from sqlalchemy import (
    Column,
    Index,
    String,
    UniqueConstraint,
)

from ichnaea.models.base import (
    _Model,
    BigIdMixin,
    CreationMixin,
    HashKey,
    HashKeyMixin,
)
from ichnaea.models.station import (
    StationMixin,
    StationBlacklistMixin,
)


class WifiKey(HashKey):

    _fields = ('key', )


class WifiKeyMixin(HashKeyMixin):

    _hashkey_cls = WifiKey

    key = Column(String(12))


class WifiMixin(BigIdMixin, WifiKeyMixin):
    pass


class Wifi(WifiMixin, StationMixin, CreationMixin, _Model):
    __tablename__ = 'wifi'

    _indices = (
        UniqueConstraint('key', name='wifi_key_unique'),
        Index('wifi_created_idx', 'created'),
        Index('wifi_new_measures_idx', 'new_measures'),
        Index('wifi_total_measures_idx', 'total_measures'),
    )

    def __init__(self, *args, **kw):
        if 'new_measures' not in kw:
            kw['new_measures'] = 0
        if 'total_measures' not in kw:
            kw['total_measures'] = 0
        super(Wifi, self).__init__(*args, **kw)

    @classmethod
    def valid_schema(cls):
        from ichnaea.data.schema import ValidWifiSchema
        return ValidWifiSchema


class WifiBlacklist(WifiMixin, StationBlacklistMixin, _Model):
    __tablename__ = 'wifi_blacklist'

    _indices = (
        UniqueConstraint('key', name='wifi_blacklist_key_unique'),
    )
