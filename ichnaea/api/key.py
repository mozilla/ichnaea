from random import randint

from repoze import lru
from sqlalchemy.orm import load_only
from sqlalchemy import (
    bindparam,
)

from ichnaea.db import BAKERY
from ichnaea.models import ApiKey
from ichnaea.models.constants import VALID_APIKEY_REGEX

_MARKER = object()

# Five minutes +/- 10% cache timeout.
API_CACHE_TIMEOUT = 300 + randint(-30, 30)
API_CACHE = lru.ExpiringLRUCache(500, default_timeout=API_CACHE_TIMEOUT)

_GET_FIELDS = (
    'valid_key', 'maxreq',
    'allow_fallback', 'allow_locate', 'allow_region', 'allow_transfer',
    'fallback_name', 'fallback_schema', 'fallback_url', 'fallback_ratelimit',
    'fallback_ratelimit_interval', 'fallback_cache_expire',
    'store_sample_submit', 'store_sample_locate',
)
_GET_QUERY = BAKERY(lambda session: session.query(ApiKey))
_GET_QUERY += lambda q: q.filter(ApiKey.valid_key == bindparam('valid_key'))
_GET_QUERY += lambda q: q.options(load_only(*_GET_FIELDS))


def empty_key():
    # Create an empty API key. This is used if API key lookup failed,
    # and the view code stills expects an API key model object.
    return Key()


def get_key(session, valid_key):
    value = API_CACHE.get(valid_key, _MARKER)
    if value is _MARKER:
        value = _GET_QUERY(session).params(valid_key=valid_key).first()
        if value is not None:
            value = Key(_model=value)
        API_CACHE.put(valid_key, value)
    return value


def validated_key(text):
    # Check length against DB column length and restrict
    # to a known set of characters.
    if (text and (3 < len(text) < 41) and
            VALID_APIKEY_REGEX.match(text)):
        return text
    return None


class Key(object):
    """
    An in-memory representation of an API key, which is not tied
    to a database session.
    """

    valid_key = None
    maxreq = 0
    allow_fallback = False
    allow_locate = True
    allow_region = True
    allow_transfer = False

    fallback_name = None
    fallback_schema = None
    fallback_url = None
    fallback_ratelimit = None
    fallback_ratelimit_interval = None
    fallback_cache_expire = None

    store_sample_locate = 100
    store_sample_submit = 100

    def __init__(self, _model=None, **kw):
        if _model is not None:
            for field in _GET_FIELDS:
                setattr(self, field, getattr(_model, field, None))
        for key, value in kw.items():
            setattr(self, key, value)

    def allowed(self, api_type):
        """
        Is this API key allowed to use the requested HTTP API?
        """
        if api_type == 'locate':
            return bool(self.allow_locate)
        elif api_type == 'region':
            return bool(self.allow_region)
        elif api_type == 'submit':
            # Submit are always allowed, even without an API key.
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
