import colander
import simplejson as json

from ichnaea.api.exceptions import (
    DailyLimitExceeded,
    InvalidAPIKey,
    ParseError,
)
from ichnaea.models.api import ApiKey
from ichnaea.rate_limit import rate_limit
from ichnaea import util
from ichnaea.webapp.view import BaseView


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

    def check(self):
        api_key = None
        api_key_text = self.request.GET.get('key', None)

        if api_key_text is None:
            self.log_count('{view_name}.no_api_key')
            if self.error_on_invalidkey:
                raise InvalidAPIKey()
        try:
            api_key = ApiKey.getkey(self.request.db_ro_session,
                                    {'valid_key': api_key_text})
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
                raise DailyLimitExceeded()
        else:
            if api_key_text is not None:
                self.log_count('{view_name}.unknown_api_key')
            if self.error_on_invalidkey:
                raise InvalidAPIKey()

        # If we failed to look up an ApiKey, create an empty one
        # rather than passing None through
        api_key = api_key or ApiKey(valid_key=None)
        return self.view(api_key)

    def preprocess_request(self):
        errors = []

        request_content = self.request.body
        if self.request.headers.get('Content-Encoding') == 'gzip':
            # handle gzip self.request bodies
            try:
                request_content = util.decode_gzip(self.request.body)
            except OSError as exc:
                errors.append({'name': None, 'description': repr(exc)})

        request_data = {}
        try:
            request_data = json.loads(
                request_content, encoding=self.request.charset)
        except ValueError as exc:
            errors.append({'name': None, 'description': repr(exc)})

        validated_data = {}
        try:
            validated_data = self.schema().deserialize(request_data)
        except colander.Invalid as exc:
            errors.append({'name': None, 'description': exc.asdict()})

        if request_content and errors:
            raise ParseError()

        return (validated_data, errors)

    def __call__(self):
        if self.check_api_key:
            return self.check()
        else:
            api_key = ApiKey(valid_key=None)
            return self.view(api_key)
