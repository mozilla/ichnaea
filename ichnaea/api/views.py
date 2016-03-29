"""
Implementation of a API specific HTTP service view.
"""

import colander
import simplejson as json
import six

from ichnaea.api.exceptions import (
    DailyLimitExceeded,
    InvalidAPIKey,
    ParseError,
)
from ichnaea.api.rate_limit import rate_limit_exceeded
from ichnaea.exceptions import GZIPDecodeError
from ichnaea.models.api import ApiKey
from ichnaea.models.constants import VALID_APIKEY_REGEX
from ichnaea import util
from ichnaea.webapp.view import BaseView

if six.PY2:  # pragma: no cover
    from ipaddr import IPAddress as ip_address  # NOQA
else:  # pragma: no cover
    from ipaddress import ip_address


class BaseAPIView(BaseView):
    """Common base class for all API related views."""

    check_api_key = True  #: Should API keys be checked?
    error_on_invalidkey = True  #: Deny access for invalid API keys?
    metric_path = None  #: Dotted URL path, for example v1.submit.
    schema = None  #: An instance of a colander schema to validate the data.
    view_type = None  #: The type of view, for example submit or locate.

    def __init__(self, request):
        super(BaseAPIView, self).__init__(request)
        self.raven_client = request.registry.raven_client
        self.redis_client = request.registry.redis_client
        self.stats_client = request.registry.stats_client

    def log_unique_ip(self, valid_key):
        try:
            ip = str(ip_address(self.request.client_addr))
        except ValueError:  # pragma: no cover
            ip = None
        if ip:
            redis_key = 'apiuser:{api_type}:{api_key}:{date}'.format(
                api_type=self.view_type,
                api_key=valid_key,
                date=util.utcnow().date().strftime('%Y-%m-%d'),
            )
            with self.redis_client.pipeline() as pipe:
                pipe.pfadd(redis_key, ip)
                pipe.expire(redis_key, 691200)  # 8 days
                pipe.execute()

    def log_count(self, valid_key, should_log):
        if valid_key is None:
            valid_key = 'none'

        self.stats_client.incr(
            self.view_type + '.request',
            tags=['path:' + self.metric_path,
                  'key:' + valid_key])

        if self.request.client_addr and should_log:
            try:
                self.log_unique_ip(valid_key)
            except Exception:  # pragma: no cover
                self.raven_client.captureException()

    def check(self):
        api_key = None
        api_key_text = self.parse_apikey()
        skip_check = False

        if api_key_text is None:
            self.log_count(None, False)
            if self.error_on_invalidkey:
                raise self.prepare_exception(InvalidAPIKey())

        if api_key_text is not None:
            try:
                session = self.request.db_ro_session
                api_key = ApiKey.get(session, api_key_text)
            except Exception:
                # if we cannot connect to backend DB, skip api key check
                skip_check = True
                self.raven_client.captureException()

        if api_key is not None and api_key.should_allow(self.view_type):
            self.log_count(api_key.valid_key,
                           api_key.should_log(self.view_type))

            rate_key = 'apilimit:{key}:{path}:{time}'.format(
                key=api_key_text,
                path=self.metric_path,
                time=util.utcnow().strftime('%Y%m%d')
            )

            should_limit = rate_limit_exceeded(
                self.redis_client,
                rate_key,
                maxreq=api_key.maxreq
            )

            if should_limit:
                raise self.prepare_exception(DailyLimitExceeded())
        elif skip_check:
            pass
        else:
            if api_key_text is not None:
                self.log_count('invalid', False)
            if self.error_on_invalidkey:
                raise self.prepare_exception(InvalidAPIKey())

        # If we failed to look up an ApiKey, create an empty one
        # rather than passing None through
        api_key = api_key or ApiKey(valid_key=None,
                                    allow_fallback=False,
                                    allow_locate=True)
        return self.view(api_key)

    def parse_apikey(self):
        api_key_text = self.request.GET.get('key', None)
        # check length against DB column length and restrict
        # to a known set of characters
        if (api_key_text and (3 < len(api_key_text) < 41) and
                VALID_APIKEY_REGEX.match(api_key_text)):
            return api_key_text
        return None

    def preprocess_request(self):
        errors = []

        request_content = self.request.body
        if self.request.headers.get('Content-Encoding') == 'gzip':
            # handle gzip self.request bodies
            try:
                request_content = util.decode_gzip(self.request.body)
            except GZIPDecodeError as exc:
                errors.append({'name': None, 'description': repr(exc)})

        request_data = {}
        try:
            request_data = json.loads(
                request_content, encoding=self.request.charset)
        except ValueError as exc:
            errors.append({'name': None, 'description': repr(exc)})

        validated_data = {}
        try:
            validated_data = self.schema.deserialize(request_data)
        except colander.Invalid as exc:
            errors.append({'name': None, 'description': exc.asdict()})

        if request_content and errors:
            raise self.prepare_exception(ParseError())

        return (validated_data, errors)

    def __call__(self):
        """Execute the view and return a response."""
        if self.check_api_key:
            return self.check()
        else:
            api_key = ApiKey(
                valid_key=None, allow_fallback=False, allow_locate=True)
            # Only use the unchecked API key in the request for simple
            # logging purposes.
            self.log_count(self.parse_apikey(), False)
            return self.view(api_key)
