from sqlalchemy import (
    Boolean,
    Column,
    String,
)
from sqlalchemy.dialects.mysql import (
    INTEGER as Integer,
)
from sqlalchemy.orm import load_only

from ichnaea.models.base import _Model


class ApiKey(_Model):
    """
    ApiKey model.

    The allow_fallback and fallback columns determine if and what
    fallback location provider should be used.

    The url specifies the external endpoint supporting the
    :ref:`api_geolocate_latest` API.

    Requests to the fallback service can optionally be rate limited.
    Two settings control the rate limit:

    ``ratelimit`` specifies how many requests are allowed to be made.

    ``ratelimit_interval`` specifies the interval in seconds for which
    the ``ratelimit`` number applies, so for example one could
    configure 60 requests per 60 seconds, or 86400 requests per
    86400 seconds (one day). Both would on average allow one request
    per second.

    Finally the fallback service might allow caching of results inside
    the projects own Redis cache. ``cache_expire`` specifies the number
    of seconds for which entries are allowed to be cached.
    """

    __tablename__ = 'api_key'

    valid_key = Column(String(40), primary_key=True)  #: UUID API key.
    maxreq = Column(Integer)  #: Maximum number of requests per day.
    log_locate = Column(Boolean)  # unused
    log_region = Column(Boolean)  # unused
    log_submit = Column(Boolean)  # unused
    allow_fallback = Column(Boolean)  #: Use the fallback source?
    allow_locate = Column(Boolean)  #: Allow locate queries?
    shortname = Column(String(40))  #: Short descriptive name.

    fallback_name = Column(String(40))  #: Fallback metric name.
    fallback_url = Column(String(256))  #: URL of the fallback provider.
    fallback_ratelimit = Column(Integer)  #: Fallback rate limit count.
    fallback_ratelimit_interval = Column(Integer)  #: Interval in seconds.
    fallback_cache_expire = Column(Integer)  #: Cache expiry in seconds.

    _get_fields = (
        'valid_key', 'maxreq', 'allow_fallback', 'allow_locate',
        'fallback_name', 'fallback_url', 'fallback_ratelimit',
        'fallback_ratelimit_interval', 'fallback_cache_expire',
    )

    @classmethod
    def get(cls, session, valid_key):
        return (session.query(cls)
                       .filter(cls.valid_key == valid_key)
                       .options(load_only(*cls._get_fields))).first()

    def allowed(self, api_type):
        """
        Is this API key allowed to use the requested HTTP API?
        """
        if api_type == 'locate':
            return bool(self.allow_locate)
        elif api_type in ('region', 'submit'):
            # Region and submit are always allowed, even without an API key.
            return True
        return None

    def can_fallback(self):
        """
        Is this API key allowed to use the fallback location provider
        and is its configuration complete?
        """
        return bool(self.allow_fallback and
                    self.fallback_name and
                    self.fallback_url and
                    self.fallback_ratelimit is not None and
                    self.fallback_ratelimit_interval)

    def should_log(self, api_type):
        # This used to differentiate between basic/extended logging
        # for each API type (locate, region, submit).
        if self.valid_key:
            return True
        return False

    def __str__(self):
        return '<ApiKey>: %s' % self.valid_key
