from enum import IntEnum
from sqlalchemy import (
    Column,
    Date,
    Unicode,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import INTEGER as Integer

from ichnaea.models.base import (
    _Model,
    IdMixin,
)
from ichnaea.models.sa_types import TinyIntEnum
from ichnaea import util


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
    )

    # tracks the creation time
    time = Column(Date)
    # lat/lon * 1000, so 12.345 is stored as 12345
    lat = Column(Integer)
    lon = Column(Integer)


class Score(IdMixin, _Model):
    __tablename__ = 'score'

    _indices = (
        UniqueConstraint('userid', 'key', 'time',
                         name='score_userid_key_time_unique'),
    )

    userid = Column(Integer(unsigned=True), index=True)
    key = Column(TinyIntEnum(ScoreKey))
    time = Column(Date)
    value = Column(Integer)

    def __init__(self, *args, **kw):
        if 'time' not in kw:
            kw['time'] = util.utcnow().date()
        super(Score, self).__init__(*args, **kw)


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
