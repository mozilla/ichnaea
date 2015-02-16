from collections import namedtuple

from sqlalchemy import (
    Column,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import (
    BIGINT as BigInteger,
    DOUBLE as Double,
    INTEGER as Integer,
)

from ichnaea.models.sa_types import TZDateTime as DateTime
from ichnaea import util

from ichnaea.models.base import _Model

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


class Wifi(_Model):
    __tablename__ = 'wifi'
    __table_args__ = (
        UniqueConstraint('key', name='wifi_key_unique'),
        Index('wifi_created_idx', 'created'),
        Index('wifi_new_measures_idx', 'new_measures'),
        Index('wifi_total_measures_idx', 'total_measures'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
        }
    )

    id = Column(BigInteger(unsigned=True),
                primary_key=True, autoincrement=True)
    created = Column(DateTime)
    modified = Column(DateTime)
    key = Column(String(12))

    # lat/lon
    lat = Column(Double(asdecimal=False))
    max_lat = Column(Double(asdecimal=False))
    min_lat = Column(Double(asdecimal=False))

    lon = Column(Double(asdecimal=False))
    max_lon = Column(Double(asdecimal=False))
    min_lon = Column(Double(asdecimal=False))

    range = Column(Integer)
    new_measures = Column(Integer(unsigned=True))
    total_measures = Column(Integer(unsigned=True))

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

wifi_table = Wifi.__table__


class WifiBlacklist(_Model):
    __tablename__ = 'wifi_blacklist'
    __table_args__ = (
        UniqueConstraint('key', name='wifi_blacklist_key_unique'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
        }
    )
    id = Column(BigInteger(unsigned=True),
                primary_key=True, autoincrement=True)
    time = Column(DateTime)
    key = Column(String(12))
    count = Column(Integer)

    def __init__(self, *args, **kw):
        if 'time' not in kw:
            kw['time'] = util.utcnow()
        if 'count' not in kw:
            kw['count'] = 1
        super(WifiBlacklist, self).__init__(*args, **kw)
