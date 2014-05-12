from functools import wraps

from ichnaea.heka_logging import get_heka_client
from pyramid.httpexceptions import HTTPBadRequest
from ichnaea.models import (
    ApiKey
)
from ichnaea.decimaljson import dumps

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
            else:
                session = request.db_slave_session
                found_key_filter = session.query(ApiKey).filter(
                    ApiKey.valid_key == api_key)
                if found_key_filter.count():
                    heka_client.incr('%s.api_key.%s' % (
                        func_name, api_key.replace('.', '__')))
                else:
                    heka_client.incr('%s.unknown_api_key' % func_name)

            return func(request, *args, **kwargs)
        return closure
    return c
