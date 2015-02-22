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
from sqlalchemy.sql import and_, or_

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


class HashKeyMixin(object):

    _hashkey_cls = None

    @classmethod
    def _to_hashkey(cls, *args, **kw):
        if args:
            obj = args[0]
        else:
            obj = kw
        if isinstance(obj, cls._hashkey_cls):
            return obj
        fields = cls._hashkey_cls._fields
        if isinstance(obj, dict):
            return cls._hashkey_cls(**obj)
        values = {}
        for field in fields:
            values[field] = getattr(obj, field, None)
        return cls._hashkey_cls(**values)

    @classmethod
    def to_hashkey(cls, *args, **kw):
        return cls._to_hashkey(*args, **kw)

    def hashkey(self):
        return self._to_hashkey(self)

    @classmethod
    def joinkey(cls, key):
        if not isinstance(key, HashKey):
            key = cls.to_hashkey(key)
        criterion = ()
        for field in cls._hashkey_cls._fields:
            value = getattr(key, field, None)
            if value is not None:
                criterion += (getattr(cls, field) == value, )
        return criterion

    @classmethod
    def querykey(cls, session, key):
        return session.query(cls).filter(*cls.joinkey(key))

    @classmethod
    def querykeys(cls, session, keys):
        if not keys:  # pragma: no cover
            # prevent construction of queries without a key restriction
            raise ValueError('Model.querykeys called with empty keys.')

        if len(cls._hashkey_cls._fields) == 1:
            # optimize queries for hashkeys with single fields to use
            # a 'WHERE model.somefield IN (:key_1, :key_2)' query
            field = cls._hashkey_cls._fields[0]
            key_list = []
            for key in keys:
                key_list.append(getattr(key, field))
            return session.query(cls).filter(getattr(cls, field).in_(key_list))

        key_filters = []
        for key in keys:
            # create a list of 'and' criteria for each hash key component
            key_filters.append(and_(*cls.joinkey(key)))
        return session.query(cls).filter(or_(*key_filters))


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
