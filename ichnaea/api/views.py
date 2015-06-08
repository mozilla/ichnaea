from pyramid.httpexceptions import HTTPBadRequest, HTTPForbidden

from ichnaea.customjson import dumps
from ichnaea.models.api import ApiKey
from ichnaea.rate_limit import rate_limit
from ichnaea.api.error import DAILY_LIMIT
from ichnaea import util
from ichnaea.webapp.view import BaseView

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


class BaseAPIView(BaseView):

    check_api_key = True
    error_on_invalidkey = True

    def __init__(self, request):
        super(BaseAPIView, self).__init__(request)
        self.raven_client = request.registry.raven_client
        self.redis_client = request.registry.redis_client
        self.stats_client = request.registry.stats_client

    def log_count(self, msg, **kw):
        self.stats_client.incr(msg.format(view_name=self.view_name, **kw))

    def forbidden(self):
        response = HTTPForbidden()
        response.content_type = 'application/json'
        response.body = DAILY_LIMIT
        return response

    def invalid_api_key(self):
        response = HTTPBadRequest()
        response.content_type = 'application/json'
        response.body = INVALID_API_KEY
        return response

    def check(self):
        api_key = None
        api_key_text = self.request.GET.get('key', None)

        if api_key_text is None:
            self.log_count('{view_name}.no_api_key')
            if self.error_on_invalidkey:
                return self.invalid_api_key()
        try:
            api_key = ApiKey.getkey(self.request.db_ro_session,
                                    api_key_text)
        except Exception:  # pragma: no cover
            # if we cannot connect to backend DB, skip api key check
            self.raven_client.captureException()

        if api_key is not None:
            self.log_count('{view_name}.api_key.{api_key}',
                           api_key=api_key.name)

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
                return self.forbidden()
        else:
            if api_key_text is not None:
                self.log_count('{view_name}.unknown_api_key')
            if self.error_on_invalidkey:
                return self.invalid_api_key()

        # If we failed to look up an ApiKey, create an empty one
        # rather than passing None through
        api_key = api_key or ApiKey(valid_key=None)
        return self.view(api_key)

    def __call__(self):
        if self.check_api_key:
            return self.check()
        else:
            api_key = ApiKey(valid_key=None)
            return self.view(api_key)
