import datetime
from functools import wraps

from ichnaea.heka_logging import get_heka_client
from pyramid.httpexceptions import HTTPBadRequest, HTTPForbidden
from ichnaea.models import (
    ApiKey
)
from ichnaea.decimaljson import dumps
from ichnaea.service.error import DAILY_LIMIT
import redis

NO_API_KEY = {
    "error": {
        "errors": [{
            "domain": "usageLimits",
            "reason": "keyInvalid",
            "message": "No API key was found",
        }],
        "code": 400,
        "message": "No API key",
    }
}
NO_API_KEY = dumps(NO_API_KEY)


def rate_limit(func_name, api_key, maxreq=0, expire=86400):
    if maxreq == 0:
        return False

    dstamp = datetime.date.today().strftime("%Y%m%d")
    key = "%s:%s:%s" % (func_name, api_key, dstamp)
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    current = r.get(key)
    if current is None or int(current) < maxreq:
        pipe = r.pipeline()
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
                    result = HTTPBadRequest()
                    result.content_type = 'application/json'
                    result.body = NO_API_KEY
                    return result

            session = request.db_slave_session
            found_key_filter = session.query(ApiKey).filter(
                ApiKey.valid_key == api_key)
            found_key = found_key_filter.first()
            if found_key:
                heka_client.incr('%s.api_key.%s' % (
                    func_name, api_key.replace('.', '__')))
                if rate_limit(func_name, api_key, found_key.maxreq):
                    result = HTTPForbidden()
                    result.content_type = 'application/json'
                    result.body = DAILY_LIMIT
                    return result
            else:
                heka_client.incr('%s.unknown_api_key' % func_name)

            return func(request, *args, **kwargs)
        return closure
    return c
