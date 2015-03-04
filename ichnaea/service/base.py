from functools import wraps

from pyramid.httpexceptions import HTTPBadRequest, HTTPForbidden
from redis import ConnectionError
from sqlalchemy import text

from ichnaea.customjson import dumps
from ichnaea.service.error import DAILY_LIMIT
from ichnaea import util

API_CHECK = text('select maxreq, log, shortname from api_key '
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

    try:
        current = redis_client.get(key)
        if current is None or int(current) < maxreq:
            pipe = redis_client.pipeline()
            pipe.incr(key, 1)
            # Expire keys after 24 hours
            pipe.expire(key, expire)
            pipe.execute()
            return False
    except ConnectionError:  # pragma: no cover
        # If we cannot connect to Redis, disable rate limitation.
        return None
    return True


def check_api_key(func_name, error_on_invalidkey=True):
    def c(func):
        @wraps(func)
        def closure(request, *args, **kwargs):
            api_key = request.GET.get('key', None)
            raven_client = request.registry.raven_client
            stats_client = request.registry.stats_client

            if api_key is None:
                stats_client.incr('%s.no_api_key' % func_name)
                if error_on_invalidkey:
                    return invalid_api_key_response()

            session = request.db_ro_session
            try:
                result = session.execute(API_CHECK.bindparams(api_key=api_key))
                found_key = result.fetchone()
            except Exception:  # pragma: no cover
                # if we cannot connect to backend DB, skip api key check
                raven_client.captureException()
                stats_client.incr('%s.dbfailure_skip_api_key' % func_name)
                return func(request, *args, **kwargs)

            if found_key is not None:
                maxreq, api_key_log, shortname = found_key
                if not shortname:  # pragma: no cover
                    shortname = api_key

                # remember api key and shortname on the request
                request.api_key_log = bool(api_key_log)
                request.api_key_name = shortname

                stats_client.incr('%s.api_key.%s' % (func_name, shortname))
                should_limit = rate_limit(request.registry.redis_client,
                                          api_key, maxreq=maxreq)
                if should_limit:
                    result = HTTPForbidden()
                    result.content_type = 'application/json'
                    result.body = DAILY_LIMIT
                    return result
                elif should_limit is None:  # pragma: no cover
                    # We couldn't connect to Redis
                    stats_client.incr('%s.redisfailure_skip_limit' % func_name)
            else:
                stats_client.incr('%s.unknown_api_key' % func_name)
                if error_on_invalidkey:
                    return invalid_api_key_response()

                # provide the same api log/name attributes
                request.api_key_log = False
                request.api_key_name = None

            return func(request, *args, **kwargs)
        return closure
    return c
