from sqlalchemy import (
    Column,
    Boolean,
    String,
)
from sqlalchemy.dialects.mysql import (
    INTEGER as Integer,
)
from sqlalchemy.orm import load_only

from ichnaea.models.base import _Model
from ichnaea.models.hashkey import (
    HashKey,
    HashKeyQueryMixin,
)


class ApiHashKey(HashKey):

    _fields = ('valid_key', )


class ApiKey(HashKeyQueryMixin, _Model):
    __tablename__ = 'api_key'

    _hashkey_cls = ApiHashKey
    _query_batch = 100
    _essential_columns = ('valid_key', 'maxreq', 'log', 'shortname')

    valid_key = Column(String(40), primary_key=True)

    # Maximum number of requests per day
    maxreq = Column(Integer)
    # Extended logging enabled?
    log = Column(Boolean)
    # Allow this API key to make external fallback calls
    allow_fallback = Column(Boolean)
    # A readable short name used in metrics
    shortname = Column(String(40))
    # A contact address
    email = Column(String(255))
    # Some free form context / description
    description = Column(String(255))

    @property
    def name(self):
        return self.shortname or self.valid_key

    def __str__(self):  # pragma: no cover
        return self.name

    @classmethod
    def querykey(cls, session, key):
        if key is None:  # pragma: no cover
            return None
        # by default exclude the long email/description string fields
        return (session.query(cls)
                       .filter(*cls.joinkey(key))
                       .options(load_only(*cls._essential_columns)))
