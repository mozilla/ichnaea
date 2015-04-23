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


class Stat(IdMixin, _Model):
    __tablename__ = 'stat'

    _indices = (
        UniqueConstraint('key', 'time', name='stat_key_time_unique'),
    )

    key = Column(TinyIntEnum(StatKey))
    time = Column(Date)
    value = Column(Integer(unsigned=True))


class User(IdMixin, _Model):
    __tablename__ = 'user'

    _indices = (
        UniqueConstraint('nickname', name='user_nickname_unique'),
    )

    nickname = Column(Unicode(128))
    email = Column(Unicode(255))
