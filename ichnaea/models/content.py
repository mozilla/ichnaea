import base64
import struct

from enum import IntEnum
from sqlalchemy import (
    BINARY,
    Column,
    Date,
    Index,
    PrimaryKeyConstraint,
    String,
    Unicode,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import (
    BIGINT as BigInteger,
    INTEGER as Integer,
)
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.types import TypeDecorator

from ichnaea.models.base import _Model
from ichnaea.models.hashkey import (
    HashKey,
    HashKeyQueryMixin,
)
from ichnaea.models.sa_types import TinyIntEnum

DATAMAP_GRID_SCALE = 1000
DATAMAP_GRID_STRUCT = struct.Struct('!II')
"""
A compact representation of a lat/lon grid as a byte sequence.

Consists of two unsigned 32 bit integers to encode both the scaled
latitude and longitude each moved to the positive space by adding
90000 / 180000.
"""

DATAMAP_SHARDS = {}


class ScoreKey(IntEnum):
    location = 0
    # 1 was new_location, denoting 10x10m areas
    new_cell = 2
    new_wifi = 3


class StatKey(IntEnum):
    """An integer enum representing a statistical value."""

    # location = 0
    cell = 1
    unique_cell = 2
    wifi = 3
    unique_wifi = 4
    # deleted_cell = 5
    # deleted_wifi = 6
    unique_cell_ocid = 7
    blue = 8
    unique_blue = 9


def decode_datamap_grid(value, scale=False, codec=None):
    """
    Decode a byte sequence representing a datamap grid into a tuple
    of a scaled latitude and longitude.

    If ``codec='base64'``, decode the value from a base64 sequence first.
    """
    if codec == 'base64':
        value = base64.b64decode(value)
    lat, lon = DATAMAP_GRID_STRUCT.unpack(value)
    lat, lon = (lat - 90000, lon - 180000)
    if scale:
        lat = float(lat) / DATAMAP_GRID_SCALE
        lon = float(lon) / DATAMAP_GRID_SCALE
    return (lat, lon)


def encode_datamap_grid(lat, lon, scale=False, codec=None):
    """
    Given a tuple of scaled latitude/longitude integers, return a compact
    8 byte sequence representing the datamap grid.

    If ``codec='base64'``, return the value as a base64 encoded sequence.
    """
    if scale:
        lat, lon = DataMap.scale(lat, lon)
    value = DATAMAP_GRID_STRUCT.pack(lat + 90000, lon + 180000)
    if codec == 'base64':
        value = base64.b64encode(value)
    return value


class DataMapGridColumn(TypeDecorator):
    """A binary type storing scaled lat/lon grids."""

    impl = BINARY

    def process_bind_param(self, value, dialect):
        if isinstance(value, bytes):
            if len(value) != 8:
                raise ValueError('Invalid grid length: %r' % value)
            return value
        lat, lon = value
        return encode_datamap_grid(lat, lon)

    def process_result_value(self, value, dialect):
        if value is None:  # pragma: no cover
            return value
        return decode_datamap_grid(value)


class DataMap(object):
    """DataMap base shard model."""

    grid = Column(DataMapGridColumn(8))  #:
    created = Column(Date)  #:
    modified = Column(Date)  #:

    @declared_attr
    def __table_args__(cls):  # NOQA
        _indices = (
            PrimaryKeyConstraint('grid'),
            Index('%s_created_idx' % cls.__tablename__, 'created'),
        )
        return _indices + (cls._settings, )

    @classmethod
    def shard_id(cls, lat, lon):
        """
        Given a lat/lon return the correct shard id for this grid.

        The world is split into four shards which each have similar
        amounts of populated land mass in them. Splitting the world
        at the equator / prime meridian would result in extremely
        unbalanced shard sizes.
        """
        if lat is None or lon is None:
            return None
        if lat < 36000:
            if lon < 5000:
                return 'sw'
            else:
                return 'se'
        else:
            if lon < 5000:
                return 'nw'
            else:
                return 'ne'

    @classmethod
    def shard_model(cls, lat, lon):
        """
        Given a lat/lon return the correct DB model class for this grid.
        """
        global DATAMAP_SHARDS
        return DATAMAP_SHARDS.get(cls.shard_id(lat, lon), None)

    @classmethod
    def shards(cls):
        """Return a dict of shard id to model classes."""
        global DATAMAP_SHARDS
        return DATAMAP_SHARDS

    @classmethod
    def scale(cls, lat, lon):
        return (
            int(round(lat * DATAMAP_GRID_SCALE)),
            int(round(lon * DATAMAP_GRID_SCALE)),
        )


class DataMapNE(DataMap, _Model):
    """DataMap north-east shard."""

    __tablename__ = 'datamap_ne'

DATAMAP_SHARDS['ne'] = DataMapNE


class DataMapNW(DataMap, _Model):
    """DataMap north-west shard."""

    __tablename__ = 'datamap_nw'

DATAMAP_SHARDS['nw'] = DataMapNW


class DataMapSE(DataMap, _Model):
    """DataMap south-east shard."""

    __tablename__ = 'datamap_se'

DATAMAP_SHARDS['se'] = DataMapSE


class DataMapSW(DataMap, _Model):
    """DataMap south-west shard."""

    __tablename__ = 'datamap_sw'

DATAMAP_SHARDS['sw'] = DataMapSW


class RegionStat(_Model):
    """RegionStat model."""

    __tablename__ = 'region_stat'

    _indices = (
        PrimaryKeyConstraint('region'),
    )

    region = Column(String(2))  #:
    gsm = Column(Integer(unsigned=True))  #:
    wcdma = Column(Integer(unsigned=True))  #:
    lte = Column(Integer(unsigned=True))  #:
    blue = Column(BigInteger(unsigned=True))  #:
    wifi = Column(BigInteger(unsigned=True))  #:


class ScoreHashKey(HashKey):

    _fields = ('userid', 'key', 'time')

    @classmethod
    def _from_json_value(cls, value):
        data = value.copy()
        data['key'] = ScoreKey(data['key'])
        return cls(**data)

    def _to_json_value(self):
        value = self.__dict__.copy()
        value['key'] = int(value['key'])
        return value


class Score(HashKeyQueryMixin, _Model):
    __tablename__ = 'score'

    _indices = (
        PrimaryKeyConstraint('key', 'userid', 'time'),
    )
    _hashkey_cls = ScoreHashKey

    # this is a foreign key to user.id
    userid = Column(Integer(unsigned=True), autoincrement=False)
    key = Column(TinyIntEnum(ScoreKey), autoincrement=False)
    time = Column(Date)
    value = Column(Integer)


class StatCounter(object):

    def __init__(self, stat_key, day):
        self.stat_key = stat_key
        self.day = day
        self.redis_key = self._key(stat_key, day)

    def _key(self, stat_key, day):
        return 'statcounter_{key}_{date}'.format(
            key=stat_key.name,
            date=day.strftime('%Y%m%d'))

    def get(self, redis_client):
        return int(redis_client.get(self.redis_key) or 0)

    def decr(self, pipe, amount):
        pipe.decr(self.redis_key, amount)
        pipe.expire(self.redis_key, 172800)  # 2 days

    def incr(self, pipe, amount):
        # keep track of newly inserted observations in redis
        pipe.incr(self.redis_key, amount)
        pipe.expire(self.redis_key, 172800)  # 2 days


class Stat(_Model):
    """Stat model."""

    __tablename__ = 'stat'

    _indices = (
        PrimaryKeyConstraint('key', 'time'),
    )

    key = Column(TinyIntEnum(StatKey), autoincrement=False)  #:
    time = Column(Date)  #:
    value = Column(BigInteger(unsigned=True))  #:


class User(_Model):
    __tablename__ = 'user'

    _indices = (
        UniqueConstraint('nickname', name='user_nickname_unique'),
    )

    # id serves as a foreign key for score.userid
    id = Column(Integer(unsigned=True), primary_key=True, autoincrement=True)
    nickname = Column(Unicode(128))
    email = Column(Unicode(255))
