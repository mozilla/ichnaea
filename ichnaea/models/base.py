from colander import Invalid
from sqlalchemy import Column
from sqlalchemy.dialects.mysql import (
    BIGINT as BigInteger,
    DOUBLE as Double,
    INTEGER as Integer,
)
from sqlalchemy.ext.declarative import (
    declared_attr,
    declarative_base,
)

from ichnaea.models.sa_types import TZDateTime as DateTime

MYSQL_SETTINGS = {
    'mysql_engine': 'InnoDB',
    'mysql_charset': 'utf8',
}


class BaseModel(object):

    _indices = ()
    _settings = MYSQL_SETTINGS

    @declared_attr
    def __table_args__(cls):  # NOQA
        return cls._indices + (cls._settings, )


_Model = declarative_base(cls=BaseModel)


class ValidationMixin(object):

    @classmethod
    def valid_schema(cls):  # pragma: no cover
        raise NotImplementedError

    @classmethod
    def validate(cls, entry):
        try:
            validated = cls.valid_schema()().deserialize(entry)
        except Invalid:
            validated = None
        return validated


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
