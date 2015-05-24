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


def check_api_key():
    def c(func):
        @wraps(func)
        def closure(self, *args, **kwargs):
            api_key = None
            api_key_text = self.request.GET.get('key', None)

            if api_key_text is None:
                self.stats_client.incr('%s.no_api_key' % self.view_name)
                if self.error_on_invalidkey:
                    return self.invalid_api_key()
            try:
                api_key = ApiKey.getkey(self.request.db_ro_session,
                                        api_key_text)
            except Exception:  # pragma: no cover
                # if we cannot connect to backend DB, skip api key check
                self.raven_client.captureException()
                self.stats_client.incr(
                    '%s.dbfailure_skip_api_key' % self.view_name)

            if api_key is not None:
                self.stats_client.incr(
                    '%s.api_key.%s' % (self.view_name, api_key.name))
                rate_key = 'apilimit:{key}:{time}'.format(
                    key=api_key_text,
                    time=util.utcnow().strftime('%Y%m%d')
                )

                should_limit = rate_limit(
                    self.redis_client,
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
                    self.stats_client.incr(
                        '%s.redisfailure_skip_limit' % self.view_name)
            else:
                if api_key_text is not None:
                    self.stats_client.incr(
                        '%s.unknown_api_key' % self.view_name)
                if self.error_on_invalidkey:
                    return self.invalid_api_key()

            # If we failed to look up an ApiKey, create an empty one
            # rather than passing None through
            api_key = api_key or ApiKey(valid_key=None)

            return func(self, api_key, *args, **kwargs)
        return closure
    return c


class BaseServiceView(object):

    route = None

    @classmethod
    def configure(cls, config):
        path = cls.route
        name = path.lstrip('/').replace('/', '_')
        config.add_route(name, path)
        config.add_view(cls, route_name=name, renderer='json')

    def __init__(self, request):
        self.request = request

    def __call__(self):  # pragma: no cover
        raise NotImplementedError()


class BaseAPIView(BaseServiceView):

    error_on_invalidkey = True

    def __init__(self, request):
        super(BaseAPIView, self).__init__(request)
        self.raven_client = request.registry.raven_client
        self.redis_client = request.registry.redis_client
        self.stats_client = request.registry.stats_client

    def invalid_api_key(self):
        response = HTTPBadRequest()
        response.content_type = 'application/json'
        response.body = INVALID_API_KEY
        return response
