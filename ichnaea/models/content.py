from enum import IntEnum
from sqlalchemy import (
    Column,
    Date,
    Unicode,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import INTEGER as Integer

from ichnaea.models.base import _Model
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


class MapStat(_Model):
    __tablename__ = 'mapstat'
    __table_args__ = (
        UniqueConstraint('lat', 'lon',
                         name='mapstat_lat_lon_unique'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
        }
    )
    id = Column(Integer(unsigned=True),
                primary_key=True, autoincrement=True)
    # tracks the creation time
    time = Column(Date)
    # lat/lon * 1000, so 12.345 is stored as 12345
    lat = Column(Integer)
    lon = Column(Integer)

mapstat_table = MapStat.__table__


class Score(_Model):
    __tablename__ = 'score'
    __table_args__ = (
        UniqueConstraint('userid', 'key', 'time',
                         name='score_userid_key_time_unique'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
        }
    )

    id = Column(Integer(unsigned=True),
                primary_key=True, autoincrement=True)
    userid = Column(Integer(unsigned=True), index=True)
    key = Column(TinyIntEnum(ScoreKey))
    time = Column(Date)
    value = Column(Integer)

    def __init__(self, *args, **kw):
        if 'time' not in kw:
            kw['time'] = util.utcnow().date()
        super(Score, self).__init__(*args, **kw)

score_table = Score.__table__


class Stat(_Model):
    __tablename__ = 'stat'
    __table_args__ = (
        UniqueConstraint('key', 'time', name='stat_key_time_unique'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
        }
    )

    id = Column(Integer(unsigned=True),
                primary_key=True, autoincrement=True)
    key = Column(TinyIntEnum(StatKey))
    time = Column(Date)
    value = Column(Integer(unsigned=True))


stat_table = Stat.__table__


class User(_Model):
    __tablename__ = 'user'
    __table_args__ = (
        UniqueConstraint('nickname', name='user_nickname_unique'),
        {
            'mysql_engine': 'InnoDB',
            'mysql_charset': 'utf8',
        }
    )

    id = Column(Integer(unsigned=True),
                primary_key=True, autoincrement=True)
    nickname = Column(Unicode(128))
    email = Column(Unicode(255))

user_table = User.__table__
