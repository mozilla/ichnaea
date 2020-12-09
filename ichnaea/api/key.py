from random import randint, random

from repoze import lru
from sqlalchemy import select

from ichnaea.models import ApiKey
from ichnaea.models.constants import VALID_APIKEY_REGEX

_MARKER = object()

# Five minutes +/- 10% cache timeout.
API_CACHE_TIMEOUT = 300 + randint(-30, 30)
API_CACHE = lru.ExpiringLRUCache(500, default_timeout=API_CACHE_TIMEOUT)

API_KEY_COLUMN_NAMES = (
    "valid_key",
    "maxreq",
    "allow_fallback",
    "allow_locate",
    "allow_region",
    "fallback_name",
    "fallback_schema",
    "fallback_url",
    "fallback_ratelimit",
    "fallback_ratelimit_interval",
    "fallback_cache_expire",
    "store_sample_submit",
    "store_sample_locate",
)


def get_key(session, valid_key):
    value = API_CACHE.get(valid_key, _MARKER)
    if value is _MARKER:
        columns = ApiKey.__table__.c
        fields = [getattr(columns, f) for f in API_KEY_COLUMN_NAMES]
        row = (
            session.execute(select(fields).where(columns.valid_key == valid_key))
        ).fetchone()
        if row is not None:
            # Create Key from sqlalchemy.engine.result.RowProxy
            value = Key(**dict(row.items()))
        else:
            value = None
        API_CACHE.put(valid_key, value)
    return value


def validated_key(text):
    # Check length against DB column length and restrict
    # to a known set of characters.
    if text and (3 < len(text) < 41) and VALID_APIKEY_REGEX.match(text):
        return text
    return None


class Key(object):
    """
    An in-memory representation of an API key, which is not tied
    to a database session.

    Class level defaults represent the values used if the API key
    lookup fails because of a database connection problem.
    """

    valid_key = None
    maxreq = 0
    allow_fallback = False
    allow_locate = True
    allow_region = True

    fallback_name = None
    fallback_schema = None
    fallback_url = None
    fallback_ratelimit = None
    fallback_ratelimit_interval = None
    fallback_cache_expire = None

    store_sample_locate = 100
    store_sample_submit = 100

    def __init__(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)

    def allowed(self, api_type):
        """
        Is this API key allowed to use the requested HTTP API?
        """
        if api_type == "locate":
            return bool(self.allow_locate)
        elif api_type == "region":
            return bool(self.allow_region)
        elif api_type == "submit":
            # Submit are always allowed, even without an API key.
            return True
        return None

    def can_fallback(self):
        """
        Is this API key allowed to use the fallback location provider
        and is its configuration complete?
        """
        return bool(
            self.allow_fallback
            and self.fallback_name
            and self.fallback_url
            and self.fallback_ratelimit is not None
            and self.fallback_ratelimit_interval
        )

    def store_sample(self, api_type, global_locate_sample_rate=100.0):
        """
        Determine if an API request should result in the data to be
        stored for further processing.

        This allows one to store only some percentage of the incoming
        locate or submit requests for a given API key.

        A global_locate_sample_rate, 0.0 to 100.0, is used to further
        reduce samples when the backend is overloaded.
        """
        if api_type == "locate":
            sample_rate = (self.store_sample_locate or 0.0) / 100.0
            sample_rate *= global_locate_sample_rate / 100.0
        elif api_type == "submit":
            sample_rate = float(self.store_sample_submit or 0.0) / 100.0
        else:
            return False

        if sample_rate <= 0.0:
            return False

        if sample_rate >= random():
            return True
        return False
