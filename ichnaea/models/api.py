from random import randint

from repoze import lru
from sqlalchemy import (
    bindparam,
    Boolean,
    Column,
    String,
)
from sqlalchemy.dialects.mysql import (
    INTEGER as Integer,
    TINYINT as TinyInteger,
)
from sqlalchemy.orm import load_only

from ichnaea.models.base import _Model
from ichnaea.db import BAKERY

# Five minutes +/- 10% cache timeout.
API_CACHE_TIMEOUT = 300 + randint(-30, 30)
API_CACHE = lru.ExpiringLRUCache(100, default_timeout=API_CACHE_TIMEOUT)

_GET_FIELDS = (
    'valid_key', 'maxreq',
    'allow_fallback', 'allow_locate', 'allow_transfer',
    'fallback_name', 'fallback_url', 'fallback_ratelimit',
    'fallback_ratelimit_interval', 'fallback_cache_expire',
    'store_sample_submit', 'store_sample_locate',
)
_GET_QUERY = BAKERY(lambda session: session.query(ApiKey))
_GET_QUERY += lambda q: q.filter(ApiKey.valid_key == bindparam('valid_key'))
_GET_QUERY += lambda q: q.options(load_only(*_GET_FIELDS))

_MARKER = object()


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

    valid_key = Column(String(40), primary_key=True)  # UUID API key.
    maxreq = Column(Integer)  # Maximum number of requests per day.
    allow_fallback = Column(Boolean)  # Use the fallback source?
    allow_locate = Column(Boolean)  # Allow locate queries?
    allow_transfer = Column(Boolean)  # Allow transfer queries?
    shortname = Column(String(40))  # Short descriptive name.

    fallback_name = Column(String(40))  # Fallback metric name.
    fallback_url = Column(String(256))  # URL of the fallback provider.
    fallback_ratelimit = Column(Integer)  # Fallback rate limit count.
    fallback_ratelimit_interval = Column(Integer)  # Interval in seconds.
    fallback_cache_expire = Column(Integer)  # Cache expiry in seconds.

    store_sample_locate = Column(TinyInteger)  # Sample rate 0-100.
    store_sample_submit = Column(TinyInteger)  # Sample rate 0-100.

    @classmethod
    def get(cls, session, valid_key):
        value = API_CACHE.get(valid_key, _MARKER)
        if value is _MARKER:
            value = _GET_QUERY(session).params(valid_key=valid_key).first()
            if value is not None:
                session.expunge(value)
            API_CACHE.put(valid_key, value)
        return value

    def allowed(self, api_type):
        """
        Is this API key allowed to use the requested HTTP API?
        """
        if api_type == 'locate':
            return bool(self.allow_locate)
        elif api_type in ('region', 'submit'):
            # Region and submit are always allowed, even without an API key.
            return True
        elif api_type == 'transfer':
            return bool(self.allow_transfer)
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

    def store_sample(self, api_type):
        """
        Determine if an API request should result in the data to be
        stored for further processing.

        This allows one to store only some percentage of the incoming
        locate or submit requests for a given API key.
        """
        if api_type == 'locate':
            sample_rate = self.store_sample_locate
        elif api_type == 'submit':
            sample_rate = self.store_sample_submit
        else:
            return False

        if sample_rate is None or sample_rate <= 0:
            return False

        if sample_rate >= randint(1, 100):
            return True
        return False

    def __str__(self):
        return '<ApiKey>: %s' % self.valid_key
