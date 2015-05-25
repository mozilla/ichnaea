import colander
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

from ichnaea.models import constants
from ichnaea.models.schema import (
    CopyingSchema,
    DateTimeFromString,
    FieldSchema,
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

    _valid_schema = None

    @classmethod
    def validate(cls, entry, _raise_invalid=False, **kw):
        try:
            validated = cls._valid_schema().deserialize(entry, **kw)
        except colander.Invalid:
            if _raise_invalid:  # pragma: no cover
                raise
            validated = None
        return validated


class CreationMixin(ValidationMixin):

    @classmethod
    def create(cls, _raise_invalid=False, **kw):
        validated = cls.validate(kw, _raise_invalid=_raise_invalid)
        if validated is None:  # pragma: no cover
            return None
        return cls(**validated)


class BigIdMixin(object):

    id = Column(BigInteger(unsigned=True),
                primary_key=True, autoincrement=True)


class IdMixin(object):

    id = Column(Integer(unsigned=True),
                primary_key=True, autoincrement=True)


class ValidTimeTrackingSchema(FieldSchema, CopyingSchema):
    """A schema which validates the fields used for time tracking."""

    created = colander.SchemaNode(DateTimeFromString(), missing=None)
    modified = colander.SchemaNode(DateTimeFromString(), missing=None)


class TimeTrackingMixin(object):

    created = Column(DateTime)
    modified = Column(DateTime)


class ValidPositionSchema(FieldSchema, CopyingSchema):
    """A schema which validates the fields present in a position."""

    lat = colander.SchemaNode(
        colander.Float(),
        missing=None,
        validator=colander.Range(constants.MIN_LAT, constants.MAX_LAT))
    lon = colander.SchemaNode(
        colander.Float(),
        missing=None,
        validator=colander.Range(constants.MIN_LON, constants.MAX_LON))


class PositionMixin(object):

    lat = Column(Double(asdecimal=False))
    lon = Column(Double(asdecimal=False))
