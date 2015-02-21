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


class HashKey(object):

    _fields = ()

    def __init__(self, *args, **kw):
        values = {}
        for i, value in enumerate(args):  # pragma: no cover
            values[self._fields[i]] = value
        for field in self._fields:
            if field in kw:
                values[field] = kw[field]
            else:
                values[field] = None
        for key, value in values.items():
            setattr(self, key, value)

    @property
    def _dottedname(self):
        klass = self.__class__
        return '%s:%s' % (klass.__module__, klass.__name__)

    def __eq__(self, other):
        if isinstance(other, HashKey):
            return self.__dict__ == other.__dict__
        return False  # pragma: no cover

    def __getitem__(self, key):
        if key in self._fields:
            return getattr(self, key, None)
        raise IndexError  # pragma: no cover

    def __hash__(self):
        # emulate a tuple hash
        value = ()
        for field in self._fields:
            value += (getattr(self, field, None), )
        return hash(value)

    def __repr__(self):
        return '{cls}: {data}'.format(cls=self._dottedname, data=self.__dict__)


class ValidationMixin(object):

    @classmethod
    def valid_schema(cls):  # pragma: no cover
        raise NotImplementedError

    @classmethod
    def validate(cls, entry, **kw):
        try:
            validated = cls.valid_schema()().deserialize(entry, **kw)
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
