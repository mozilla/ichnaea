from sqlalchemy import (
    Boolean,
    Column,
    String,
)
from sqlalchemy.dialects.mysql import (
    INTEGER as Integer,
)

from ichnaea.models.base import _Model


class ApiKey(_Model):
    __tablename__ = 'api_key'

    valid_key = Column(String(40), primary_key=True)

    #: Maximum number of requests per day
    maxreq = Column(Integer)
    #: Extended logging enabled?
    log = Column(Boolean)
    #: Allow this API key to make external fallback calls
    allow_fallback = Column(Boolean)
    #: A readable short name used in metrics
    shortname = Column(String(40))

    @property
    def name(self):
        return self.shortname or self.valid_key

    def __str__(self):  # pragma: no cover
        return '<ApiKey>: %s' % self.name
