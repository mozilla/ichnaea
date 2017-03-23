"""
Model and schema related common classes.
"""

import colander
from sqlalchemy.ext.declarative import (
    declared_attr,
    declarative_base,
)

MYSQL_SETTINGS = {
    'mysql_engine': 'InnoDB',
    'mysql_charset': 'utf8',
}


class BaseModel(object):
    """A base model with a common set of database settings."""

    _indices = ()
    _settings = MYSQL_SETTINGS

    @declared_attr
    def __table_args__(cls):  # NOQA
        return cls._indices + (cls._settings, )


_Model = declarative_base(cls=BaseModel)


class HashableDict(object):
    """
    A class representing a unique combination of fields, much like a
    namedtuple. Instances of this class can be used as dictionary keys.
    """

    _fields = ()

    def __init__(self, **kw):
        for field in self._fields:
            if field in kw:
                setattr(self, field, kw[field])
            else:
                setattr(self, field, None)

    def __eq__(self, other):
        if isinstance(other, HashableDict):
            return self.__dict__ == other.__dict__
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        """
        Returns a hash of a tuple of the instance values in the same
        order as the _fields definition.
        """
        value = ()
        for field in self._fields:
            value += (getattr(self, field, None), )
        return hash(value)


class ValidationMixin(object):
    """
    A mixin to tie a class and its valid colander schema together.
    """

    _valid_schema = None

    @classmethod
    def validate(cls, entry, _raise_invalid=False, **kw):
        """
        Returns a validated subset of the passed in entry dictionary,
        based on the classes _valid_schema, otherwise returns None.
        """
        try:
            validated = cls._valid_schema.deserialize(entry, **kw)
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
