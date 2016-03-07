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
    """ApiKey model."""

    __tablename__ = 'api_key'

    valid_key = Column(String(40), primary_key=True)  #: UUID API key.
    maxreq = Column(Integer)  #: Maximum number of requests per day.
    log_locate = Column(Boolean)  # unused
    log_region = Column(Boolean)  # unused
    log_submit = Column(Boolean)  # unused
    allow_fallback = Column(Boolean)  #: Use the fallback source?
    allow_locate = Column(Boolean)  #: Allow locate queries?
    shortname = Column(String(40))  #: Short descriptive name.

    def should_allow(self, api_type):
        # Region and submit are always allowed, even without an API key.
        if api_type in ('fallback', 'locate'):
            return bool(getattr(self, 'allow_%s' % api_type, False))
        return True

    def should_log(self, api_type):
        # This used to differentiate between basic/extended logging
        # for each API type (locate, region, submit).
        if self.valid_key:
            return True
        return False

    def __str__(self):
        return '<ApiKey>: %s' % self.valid_key
