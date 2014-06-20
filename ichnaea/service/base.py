import datetime
from functools import wraps

from ichnaea.heka_logging import get_heka_client
from pyramid.httpexceptions import HTTPBadRequest, HTTPForbidden
from ichnaea.models import (
    ApiKey
)
from ichnaea.customjson import dumps
from ichnaea.service.error import DAILY_LIMIT

import redis
import urlparse

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


def rate_limit(func_name, api_key, registry, maxreq=0, expire=86400):
    if maxreq == 0:
        return False

    dstamp = datetime.date.today().strftime("%Y%m%d")
    key = "%s:%s:%s" % (func_name, api_key, dstamp)

    redis_con = registry.redis_con
    current = redis_con.get(key)
    if current is None or int(current) < maxreq:
        pipe = redis_con.pipeline()
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
                if rate_limit(request.registry, func_name,
                              api_key, found_key.maxreq):
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


def redis_con(redis_url, registry):
    r_url = urlparse.urlparse(redis_url)
    r_host = r_url.netloc.split(":")[0]
    r_port = int(r_url.netloc.split(":")[1])
    r_db = int(r_url.path[1:])
    pool = redis.ConnectionPool(max_connections=100)
    registry.redis_pool = pool
    return redis.StrictRedis(host=r_host,
                             port=r_port,
                             db=r_db,
                             connection_pool=pool)
