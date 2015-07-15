from enum import IntEnum
from sqlalchemy import (
    Column,
    Date,
    Index,
    PrimaryKeyConstraint,
    Unicode,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import (
    BIGINT as BigInteger,
    INTEGER as Integer,
)

from ichnaea.models.base import _Model
from ichnaea.models.hashkey import (
    HashKey,
    HashKeyQueryMixin,
)
from ichnaea.models.sa_types import TinyIntEnum


class ScoreKey(IntEnum):
    location = 0
    # 1 was new_location, denoting 10x10m areas
    new_cell = 2
    new_wifi = 3


class StatKey(IntEnum):
    # location = 0
    cell = 1
    unique_cell = 2
    wifi = 3
    unique_wifi = 4
    # deleted_cell = 5
    # deleted_wifi = 6
    unique_ocid_cell = 7


class MapStatHashKey(HashKey):

    _fields = ('lat', 'lon')


class MapStat(HashKeyQueryMixin, _Model):
    __tablename__ = 'mapstat'

    _indices = (
        UniqueConstraint('lat', 'lon', name='mapstat_lat_lon_unique'),
        Index('idx_mapstat_time', 'time'),
    )
    _hashkey_cls = MapStatHashKey
    _query_batch = 50
    _scaling_factor = 1000

    # used to preserve stable insert ordering
    id = Column(Integer(unsigned=True), primary_key=True, autoincrement=True)
    # tracks the creation time
    time = Column(Date)
    # lat/lon * 1000, so 12.345 is stored as 12345
    lat = Column(Integer)
    lon = Column(Integer)

    @classmethod
    def scale(cls, float_value):
        return int(float_value * cls._scaling_factor)


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
    _query_batch = 30

    # this is a foreign key to user.id
    userid = Column(Integer(unsigned=True), autoincrement=False)
    key = Column(TinyIntEnum(ScoreKey), autoincrement=False)
    time = Column(Date)
    value = Column(Integer)

    @classmethod
    def incr(cls, session, key, value):
        score = cls.getkey(session, key)
        if score is not None:
            score.value += int(value)
        else:
            stmt = cls.__table__.insert(
                on_duplicate='value = value + %s' % int(value)).values(
                userid=key.userid, key=key.key, time=key.time, value=value)
            session.execute(stmt)
        return value


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


class StatHashKey(HashKey):

    _fields = ('key', 'time')


class Stat(HashKeyQueryMixin, _Model):
    __tablename__ = 'stat'

    _indices = (
        PrimaryKeyConstraint('key', 'time'),
    )
    _hashkey_cls = StatHashKey
    _query_batch = 50

    key = Column(TinyIntEnum(StatKey), autoincrement=False)
    time = Column(Date)
    value = Column(BigInteger(unsigned=True))

    @classmethod
    def incr(cls, session, key, value, old=0):
        stat = cls.getkey(session, key)
        if stat is not None:
            stat.value += int(value)
        else:
            stmt = cls.__table__.insert(
                on_duplicate='value = value + %s' % int(value)).values(
                key=key.key, time=key.time, value=old + value)
            session.execute(stmt)
        return value


class User(_Model):
    __tablename__ = 'user'

    _indices = (
        UniqueConstraint('nickname', name='user_nickname_unique'),
    )

    # id serves as a foreign key for score.userid
    id = Column(Integer(unsigned=True), primary_key=True, autoincrement=True)
    nickname = Column(Unicode(128))
    email = Column(Unicode(255))
