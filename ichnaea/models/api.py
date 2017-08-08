from sqlalchemy import (
    Boolean,
    Column,
    String,
)
from sqlalchemy.dialects.mysql import (
    INTEGER as Integer,
    TINYINT as TinyInteger,
)

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

    valid_key = Column(String(40), primary_key=True)  # UUID API key.
    maxreq = Column(Integer)  # Maximum number of requests per day.
    allow_fallback = Column(Boolean)  # Use the fallback source?
    allow_locate = Column(Boolean)  # Allow locate queries?
    allow_region = Column(Boolean)  # Allow region queries?
    allow_transfer = Column(Boolean)  # Allow transfer queries?

    fallback_name = Column(String(40))  # Fallback metric name.
    fallback_schema = Column(String(64))  # Fallback API schema.
    fallback_url = Column(String(256))  # URL of the fallback provider.
    fallback_ratelimit = Column(Integer)  # Fallback rate limit count.
    fallback_ratelimit_interval = Column(Integer)  # Interval in seconds.
    fallback_cache_expire = Column(Integer)  # Cache expiry in seconds.

    store_sample_locate = Column(TinyInteger)  # Sample rate 0-100.
    store_sample_submit = Column(TinyInteger)  # Sample rate 0-100.
