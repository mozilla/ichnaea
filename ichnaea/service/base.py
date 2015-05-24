from functools import wraps

from pyramid.httpexceptions import HTTPBadRequest, HTTPForbidden

from ichnaea.customjson import dumps
from ichnaea.models.api import ApiKey
from ichnaea.rate_limit import rate_limit
from ichnaea.service.error import DAILY_LIMIT
from ichnaea import util

INVALID_API_KEY = {
    'error': {
        'errors': [{
            'domain': 'usageLimits',
            'reason': 'keyInvalid',
            'message': 'Missing or invalid API key.',
        }],
        'code': 400,
        'message': 'Invalid API key',
    }
}
INVALID_API_KEY = dumps(INVALID_API_KEY)


def invalid_api_key_response():
    result = HTTPBadRequest()
    result.content_type = 'application/json'
    result.body = INVALID_API_KEY
    return result


def check_api_key(func_name, error_on_invalidkey=True):
    def c(func):
        @wraps(func)
        def closure(request, *args, **kwargs):
            api_key = None
            api_key_text = request.GET.get('key', None)

            if api_key_text is None:
                request.registry.stats_client.incr('%s.no_api_key' % func_name)
                if error_on_invalidkey:
                    return invalid_api_key_response()
            try:
                api_key = ApiKey.getkey(request.db_ro_session, api_key_text)
            except Exception:  # pragma: no cover
                # if we cannot connect to backend DB, skip api key check
                request.registry.rave_client.captureException()
                request.registry.stats_client.incr(
                    '%s.dbfailure_skip_api_key' % func_name)

            if api_key is not None:
                request.registry.stats_client.incr(
                    '%s.api_key.%s' % (func_name, api_key.name))
                rate_key = 'apilimit:{key}:{time}'.format(
                    key=api_key_text,
                    time=util.utcnow().strftime('%Y%m%d')
                )

                should_limit = rate_limit(
                    request.registry.redis_client,
                    rate_key,
                    maxreq=api_key.maxreq
                )

                if should_limit:
                    response = HTTPForbidden()
                    response.content_type = 'application/json'
                    response.body = DAILY_LIMIT
                    return response
                elif should_limit is None:  # pragma: no cover
                    # We couldn't connect to Redis
                    request.registry.stats_client.incr(
                        '%s.redisfailure_skip_limit' % func_name)
            else:
                if api_key_text is not None:
                    request.registry.stats_client.incr(
                        '%s.unknown_api_key' % func_name)
                if error_on_invalidkey:
                    return invalid_api_key_response()

            # If we failed to look up an ApiKey, create an empty one
            # rather than passing None through
            api_key = api_key or ApiKey(valid_key=None)

            return func(request, api_key, *args, **kwargs)
        return closure
    return c
