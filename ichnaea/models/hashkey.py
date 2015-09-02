"""
Classes representing unique hashable keys and related database query helpers.
"""

from six import string_types
from sqlalchemy.sql import and_, or_

from ichnaea.models.base import JSONMixin

_sentinel = object()


class HashKey(JSONMixin):
    """
    A class representing a unique combination of fields, much like a
    namedtuple. Instances of this class can be used as dictionary keys.
    """

    _fields = ()  #:

    def __init__(self, **kw):
        for field in self._fields:
            if field in kw:
                setattr(self, field, kw[field])
            else:
                setattr(self, field, None)

    def __eq__(self, other):
        if isinstance(other, HashKey):
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

    def __repr__(self):
        return '{cls}: {data}'.format(cls=self._dottedname, data=self.__dict__)


class HashKeyMixin(object):
    """
    A mixin to tie a class and its unique hashkey together.
    """

    _hashkey_cls = None  #:

    @classmethod
    def _to_hashkey(cls, obj=_sentinel, **kw):
        if obj is _sentinel:
            obj = kw
        if isinstance(obj, cls._hashkey_cls):
            return obj
        if isinstance(obj, dict):
            return cls._hashkey_cls(**obj)
        if isinstance(obj, (bytes, int) + string_types):
            raise TypeError('Expected dict, hashkey or model object.')
        values = {}
        for field in cls._hashkey_cls._fields:
            values[field] = getattr(obj, field, None)
        return cls._hashkey_cls(**values)

    @classmethod
    def to_hashkey(cls, *args, **kw):
        """
        Returns the classes hashkey from a dict or keyword arguments.
        """
        return cls._to_hashkey(*args, **kw)

    def hashkey(self):
        """
        Returns a hashkey of this instance.
        """
        return self._to_hashkey(self)


class HashKeyQueryMixin(HashKeyMixin):
    """
    A database model mixin, where the classes hashkey represents
    the primary key columns of the model.
    """

    _insert_batch = 50  #:
    _query_batch = 100  #:

    @classmethod
    def joinkey(cls, key):
        """
        Create a SQLAlchemy filter criterion for doing a primary key
        lookup.
        """
        if not isinstance(key, HashKey):
            if isinstance(key, HashKeyMixin):  # pragma: no cover
                key = key.hashkey()
            else:
                key = cls.to_hashkey(key)
        criterion = ()
        for field in cls._hashkey_cls._fields:
            value = getattr(key, field, _sentinel)
            if value is not _sentinel:
                criterion += (getattr(cls, field) == value, )
        if not criterion:  # pragma: no cover
            # prevent construction of queries without a key restriction
            raise ValueError('Model.joinkey called with empty key.')
        return criterion

    @classmethod
    def getkey(cls, session, key):
        """
        Given a database session, returns the row matching the passed
        in hashkey.
        """
        if key is None:  # pragma: no cover
            return None
        return cls.querykey(session, key).first()

    @classmethod
    def querykey(cls, session, key):
        """
        Given a database session, returns a SQLAlchemy query object
        with a filter set to return the row matching the passed in
        hashkey.
        """
        if key is None:  # pragma: no cover
            return None
        return session.query(cls).filter(*cls.joinkey(key))

    @classmethod
    def _querykeys(cls, session, keys):
        # Given a database session and a list of hashkeys, returns a
        # SQLAlchemy query object with a filter set to returns the rows
        # matching the passed in hashkeys.
        if not keys:  # pragma: no cover
            # prevent construction of queries without a key restriction
            raise ValueError('Model._querykeys called with empty keys.')

        if len(cls._hashkey_cls._fields) == 1:
            # optimize queries for hashkeys with single fields to use
            # a 'WHERE model.somefield IN (:key_1, :key_2)' query
            field = cls._hashkey_cls._fields[0]
            return (session.query(cls)
                           .filter(getattr(cls, field).in_(list(keys))))

        key_filters = []
        for key in keys:
            # create a list of 'and' criteria for each hash key component
            key_filters.append(and_(*cls.joinkey(key)))
        return session.query(cls).filter(or_(*key_filters))

    @classmethod
    def iterkeys(cls, session, keys, extra=None):
        """
        Called with a database session, a list of hashkeys and an optional
        callable that will be attached to the database queries, for
        example a load_only or options.

        This is an iterator returning all the matching rows, while the
        underlying database queries are batched into chunks based on
        the classes _query_batch constant.

        Note that providing an order option via extra won't work, as
        it would only order each chunked query but won't provide a
        total order over all returned rows.
        """
        # return all the keys, but batch the actual query depending on
        # an appropriate batch size for each model
        for i in range(0, len(keys), cls._query_batch):
            query = cls._querykeys(session, keys[i:i + cls._query_batch])
            if extra is not None:
                query = extra(query)
            for instance in query.all():
                yield instance
