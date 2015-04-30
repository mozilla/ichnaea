from enum import IntEnum
from sqlalchemy import (
    Column,
    Date,
    Index,
    Unicode,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import INTEGER as Integer

from ichnaea.models.base import (
    _Model,
    IdMixin,
)
from ichnaea.models.hashkey import (
    HashKey,
    HashKeyMixin,
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


class MapStat(IdMixin, _Model):
    __tablename__ = 'mapstat'

    _indices = (
        UniqueConstraint('lat', 'lon', name='mapstat_lat_lon_unique'),
        Index('idx_mapstat_time', 'time'),
    )

    # tracks the creation time
    time = Column(Date)
    # lat/lon * 1000, so 12.345 is stored as 12345
    lat = Column(Integer)
    lon = Column(Integer)


class ScoreHashKey(HashKey):

    _fields = ('userid', 'key', 'time')


class Score(IdMixin, HashKeyMixin, _Model):
    __tablename__ = 'score'

    _indices = (
        UniqueConstraint('userid', 'key', 'time',
                         name='score_userid_key_time_unique'),
    )
    _hashkey_cls = ScoreHashKey

    userid = Column(Integer(unsigned=True), index=True)
    key = Column(TinyIntEnum(ScoreKey))
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

    def incr(self, pipe, amount):
        # keep track of newly inserted observations in redis
        pipe.incr(self.redis_key, amount)
        pipe.expire(self.redis_key, 172800)  # 2 days


class StatHashKey(HashKey):

    _fields = ('key', 'time')


class Stat(IdMixin, HashKeyMixin, _Model):
    __tablename__ = 'stat'

    _indices = (
        UniqueConstraint('key', 'time', name='stat_key_time_unique'),
    )
    _hashkey_cls = StatHashKey

    key = Column(TinyIntEnum(StatKey))
    time = Column(Date)
    value = Column(Integer(unsigned=True))

    @classmethod
    def incr(cls, session, key, old_value, value):
        stat = cls.getkey(session, key)
        if stat is not None:
            stat.value += int(value)
        else:
            stmt = cls.__table__.insert(
                on_duplicate='value = value + %s' % int(value)).values(
                key=key.key, time=key.time, value=old_value + value)
            session.execute(stmt)
        return value


class User(IdMixin, _Model):
    __tablename__ = 'user'

    _indices = (
        UniqueConstraint('nickname', name='user_nickname_unique'),
    )

    nickname = Column(Unicode(128))
    email = Column(Unicode(255))
