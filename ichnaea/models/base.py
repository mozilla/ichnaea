from sqlalchemy import Column
from sqlalchemy.dialects.mysql import (
    BIGINT as BigInteger,
    DOUBLE as Double,
    INTEGER as Integer,
)
from sqlalchemy.ext.declarative import declarative_base

from ichnaea.models.sa_types import TZDateTime as DateTime


class BaseModel(object):

    __table_args__ = {
        'mysql_engine': 'InnoDB',
        'mysql_charset': 'utf8',
    }


_Model = declarative_base(cls=BaseModel)


class BigIdMixin(object):

    id = Column(BigInteger(unsigned=True),
                primary_key=True, autoincrement=True)


class IdMixin(object):

    id = Column(Integer(unsigned=True),
                primary_key=True, autoincrement=True)


class TimeTrackingMixin(object):

    created = Column(DateTime)
    modified = Column(DateTime)


class PositionMixin(object):

    lat = Column(Double(asdecimal=False))
    lon = Column(Double(asdecimal=False))
