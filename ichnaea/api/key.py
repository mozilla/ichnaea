from random import randint, random

from cachetools import cached, TTLCache
from gevent.lock import RLock

from ichnaea.models import ApiKey
from ichnaea.models.constants import VALID_APIKEY_REGEX

_MARKER = object()

# Five minutes +/- 10% cache timeout.
API_CACHE_TIMEOUT = 300 + randint(-30, 30)
API_CACHE = TTLCache(maxsize=500, ttl=API_CACHE_TIMEOUT)
API_CACHE_LOCK = RLock()


def _cache_key(session, valid_key):
    return valid_key


@cached(API_CACHE, key=_cache_key, lock=API_CACHE_LOCK)
def get_key(session, valid_key):
    api_key = session.query(ApiKey).filter(ApiKey.valid_key == valid_key).one_or_none()
    if api_key:
        return Key.from_obj(api_key)
    return None


def validated_key(text):
    # Check length against DB column length and restrict
    # to a known set of characters.
    if text and (3 < len(text) < 41) and VALID_APIKEY_REGEX.match(text):
        return text
    return None


class Key:
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

    @classmethod
    def from_obj(cls, api_key):
        """Load from a database object."""
        return cls(
            valid_key=api_key.valid_key,
            maxreq=api_key.maxreq,
            allow_fallback=api_key.allow_fallback,
            allow_locate=api_key.allow_locate,
            allow_region=api_key.allow_region,
            fallback_name=api_key.fallback_name,
            fallback_schema=api_key.fallback_schema,
            fallback_url=api_key.fallback_url,
            fallback_ratelimit=api_key.fallback_ratelimit,
            fallback_ratelimit_interval=api_key.fallback_ratelimit_interval,
            fallback_cache_expire=api_key.fallback_cache_expire,
            store_sample_submit=api_key.store_sample_submit,
            store_sample_locate=api_key.store_sample_locate,
        )

    def as_dict(self):
        return {
            "valid_key": self.valid_key,
            "maxreq": self.maxreq,
            "allow_fallback": self.allow_fallback,
            "allow_locate": self.allow_locate,
            "allow_region": self.allow_region,
            "fallback_name": self.fallback_name,
            "fallback_schema": self.fallback_schema,
            "fallback_url": self.fallback_url,
            "fallback_ratelimit": self.fallback_ratelimit,
            "fallback_ratelimit_interval": self.fallback_ratelimit_interval,
            "fallback_cache_expire": self.fallback_cache_expire,
            "store_sample_submit": self.store_sample_submit,
            "store_sample_locate": self.store_sample_locate,
        }

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
