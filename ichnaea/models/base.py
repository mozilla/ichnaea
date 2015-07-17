"""
Model and schema related common classes.
"""

import colander
from pyramid.path import DottedNameResolver
from sqlalchemy import Column
from sqlalchemy.dialects.mysql import (
    BIGINT as BigInteger,
    DOUBLE as Double,
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
}  #: Common MySQL database settings.
RESOLVER = DottedNameResolver('ichnaea')


class BaseModel(object):
    """A base model with a common set of database settings."""

    _indices = ()  #:
    _settings = MYSQL_SETTINGS  #:

    @declared_attr
    def __table_args__(cls):  # NOQA
        return cls._indices + (cls._settings, )

_Model = declarative_base(cls=BaseModel)


class JSONMixin(object):
    """
    A mixin class that supports round-tripping of the actual class
    via our internal JSON format back into an instance of the class.
    """

    @property
    def _dottedname(self):
        """"Returns a fully qualified import path to this class."""
        klass = self.__class__
        return '%s:%s' % (klass.__module__, klass.__name__)

    @staticmethod
    def _from_json(dct):
        """Instantiate a class based on the provided JSON dictionary."""
        data = dct['__class__']
        klass = RESOLVER.resolve(data['name'])
        return klass._from_json_value(data['value'])

    @classmethod
    def _from_json_value(cls, value):
        """Instantiate this class based on the provided values."""
        return cls(**value)

    def _to_json(self):
        """"
        Returns a dictionary representation of this class dotted name
        and its instance state.
        """
        return {'__class__': {
            'name': self._dottedname,
            'value': self._to_json_value(),
        }}

    def _to_json_value(self):
        """"Returns a dictionary representation of the instance state."""
        return self.__dict__


class ValidationMixin(object):
    """
    A mixin to tie a class and its valid colander schema together.
    """

    _valid_schema = None  #:

    @classmethod
    def validate(cls, entry, _raise_invalid=False, **kw):
        """
        Returns a validated subset of the passed in entry dictionary,
        based on the classes _valid_schema, otherwise returns None.
        """
        try:
            validated = cls._valid_schema().deserialize(entry, **kw)
        except colander.Invalid:
            if _raise_invalid:  # pragma: no cover
                raise
            validated = None
        return validated


class CreationMixin(ValidationMixin):
    """
    A mixin with a custom create constructor that validates the
    keyword arguments before creating an instance of the class.
    """

    @classmethod
    def create(cls, _raise_invalid=False, **kw):
        """
        Returns an instance of this class, if the passed in keyword
        arguments passed schema validation, otherwise returns None.
        """
        validated = cls.validate(kw, _raise_invalid=_raise_invalid)
        if validated is None:  # pragma: no cover
            return None
        return cls(**validated)


class BigIdMixin(object):
    """A database model mixin representing a biginteger auto-inc id."""

    id = Column(BigInteger(unsigned=True),
                primary_key=True, autoincrement=True)


class ValidTimeTrackingSchema(FieldSchema, CopyingSchema):
    """A schema which validates the fields used for time tracking."""

    created = colander.SchemaNode(DateTimeFromString(), missing=None)
    modified = colander.SchemaNode(DateTimeFromString(), missing=None)


class TimeTrackingMixin(object):
    """A database model mixin with created and modified datetime fields."""

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
    """A database model mixin with lat and lon float fields."""

    lat = Column(Double(asdecimal=False))
    lon = Column(Double(asdecimal=False))
