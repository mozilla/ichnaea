import datetime
from functools import wraps

from ichnaea.heka_logging import get_heka_client
from pyramid.httpexceptions import HTTPBadRequest, HTTPForbidden
from ichnaea.models import (
    ApiKey
)
from ichnaea.customjson import dumps
from ichnaea.service.error import DAILY_LIMIT


INVALID_API_KEY = {
    "error": {
        "errors": [{
            "domain": "usageLimits",
            "reason": "keyInvalid",
            "message": "Missing or invalid API key.",
        }],
        "code": 400,
        "message": "Invalid API key",
    }
}
INVALID_API_KEY = dumps(INVALID_API_KEY)


def invalid_api_key_response():
    result = HTTPBadRequest()
    result.content_type = 'application/json'
    result.body = INVALID_API_KEY
    return result


def rate_limit(redis_client, func_name, api_key, maxreq=0, expire=86400):
    if not maxreq:
        return False

    dstamp = datetime.datetime.utcnow().strftime("%Y%m%d")
    key = "%s:%s:%s" % (func_name, api_key, dstamp)

    current = redis_client.get(key)
    if current is None or int(current) < maxreq:
        pipe = redis_client.pipeline()
        pipe.incr(key, 1)
        # Expire keys after 24 hours
        pipe.expire(key, expire)
        pipe.execute()
        return False
    return True


def check_api_key(func_name, error_on_invalidkey=False):
    def c(func):
        @wraps(func)
        def closure(request, *args, **kwargs):
            api_key = request.GET.get('key', None)
            heka_client = get_heka_client()

            if api_key is None:
                heka_client.incr('%s.no_api_key' % func_name)
                if error_on_invalidkey:
                    return invalid_api_key_response()

            session = request.db_slave_session
            found_key_filter = session.query(ApiKey).filter(
                ApiKey.valid_key == api_key)

            found_key = found_key_filter.first()
            if found_key:
                heka_client.incr('%s.api_key.%s' % (func_name, api_key))
                if rate_limit(request.registry.redis_client, func_name,
                              api_key, maxreq=found_key.maxreq):
                    result = HTTPForbidden()
                    result.content_type = 'application/json'
                    result.body = DAILY_LIMIT
                    return result
            else:
                heka_client.incr('%s.unknown_api_key' % func_name)
                if error_on_invalidkey:
                    return invalid_api_key_response()

            return func(request, *args, **kwargs)
        return closure
    return c
