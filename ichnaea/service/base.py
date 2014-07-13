from functools import wraps

from sqlalchemy import text

from ichnaea.customjson import dumps
from pyramid.httpexceptions import HTTPBadRequest, HTTPForbidden
from ichnaea.service.error import DAILY_LIMIT
from ichnaea.stats import get_stats_client
from ichnaea import util

API_CHECK = text('select maxreq, shortname from api_key '
                 'where valid_key = :api_key')

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


def rate_limit(redis_client, api_key, maxreq=0, expire=86400):
    if not maxreq:
        return False

    dstamp = util.utcnow().strftime("%Y%m%d")
    key = "apilimit:%s:%s" % (api_key, dstamp)

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
            stats_client = get_stats_client()

            if api_key is None:
                stats_client.incr('%s.no_api_key' % func_name)
                if error_on_invalidkey:
                    return invalid_api_key_response()

            session = request.db_slave_session
            result = session.execute(API_CHECK.bindparams(api_key=api_key))
            found_key = result.fetchone()

            if found_key is not None:
                maxreq, shortname = found_key
                if not shortname:
                    shortname = api_key
                stats_client.incr('%s.api_key.%s' % (func_name, shortname))
                if rate_limit(request.registry.redis_client,
                              api_key, maxreq=maxreq):
                    result = HTTPForbidden()
                    result.content_type = 'application/json'
                    result.body = DAILY_LIMIT
                    return result
            else:
                stats_client.incr('%s.unknown_api_key' % func_name)
                if error_on_invalidkey:
                    return invalid_api_key_response()

            return func(request, *args, **kwargs)
        return closure
    return c
