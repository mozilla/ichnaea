from functools import wraps

from ichnaea.heka_logging import get_heka_client
from pyramid.httpexceptions import HTTPBadRequest
from ichnaea.models import (
    ApiKey
)
from ichnaea.customjson import dumps

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
            else:
                session = request.db_slave_session
                found_key_filter = session.query(ApiKey).filter(
                    ApiKey.valid_key == api_key)
                if found_key_filter.count():
                    heka_client.incr('%s.api_key.%s' % (func_name, api_key))
                else:
                    heka_client.incr('%s.unknown_api_key' % func_name)
                    if error_on_invalidkey:
                        return invalid_api_key_response()

            return func(request, *args, **kwargs)
        return closure
    return c
