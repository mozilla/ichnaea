"""
Implementation of a API specific HTTP service view.
"""

import json

import colander
from ipaddress import ip_address
import markus
from redis import RedisError

from ichnaea.api.exceptions import DailyLimitExceeded, InvalidAPIKey, ParseError
from ichnaea.api.key import get_key, Key, validated_key
from ichnaea.exceptions import GZIPDecodeError
from ichnaea import util
from ichnaea.webapp.view import BaseView


METRICS = markus.get_metrics()


class BaseAPIView(BaseView):
    """Common base class for all API related views."""

    error_on_invalidkey = True  # Deny access for invalid API keys?
    ip_log_and_rate_limit = True  # Count unique IP addresses and track limits?
    metric_path = None  # Dotted URL path, for example v1.submit.
    schema = None  # An instance of a colander schema to validate the data.
    view_type = None  # The type of view, for example submit or locate.

    def __init__(self, request):
        super(BaseAPIView, self).__init__(request)
        self.raven_client = request.registry.raven_client
        self.redis_client = request.registry.redis_client

    def parse_apikey(self):
        try:
            api_key_text = self.request.GET.get("key", None)
        except Exception:
            api_key_text = None
        # Validate key and potentially return None
        return validated_key(api_key_text)

    def log_count(self, valid_key):
        METRICS.incr(
            self.view_type + ".request",
            tags=["path:" + self.metric_path, "key:" + valid_key],
        )

    def log_ip_and_rate_limited(self, valid_key, maxreq):
        # Log IP
        addr = self.request.client_addr
        if not addr:
            # Use localhost as a marker
            addr = "127.0.0.1"
        if isinstance(addr, bytes):
            addr = addr.decode("ascii")
        try:
            ip = str(ip_address(addr))
        except ValueError:
            ip = "127.0.0.1"

        now = util.utcnow()
        log_ip_key = "apiuser:{api_type}:{key}:{date}".format(
            api_type=self.view_type, key=valid_key, date=now.date().strftime("%Y-%m-%d")
        )
        rate_key = "apilimit:{key}:{path}:{time}".format(
            key=valid_key, path=self.metric_path, time=now.strftime("%Y%m%d")
        )

        should_limit = False
        try:
            with self.redis_client.pipeline() as pipe:
                pipe.pfadd(log_ip_key, ip)
                pipe.expire(log_ip_key, 691200)  # 8 days
                pipe.incr(rate_key, 1)
                pipe.expire(rate_key, 90000)  # 25 hours
                _, _, count, _ = pipe.execute()
                if maxreq and count > maxreq:
                    should_limit = True
        except RedisError:
            self.raven_client.captureException()

        return should_limit

    def preprocess_request(self):
        errors = []

        request_content = self.request.body
        if self.request.headers.get("Content-Encoding") == "gzip":
            # handle gzip self.request bodies
            try:
                request_content = util.decode_gzip(self.request.body)
            except GZIPDecodeError as exc:
                errors.append({"name": None, "description": repr(exc)})

        if isinstance(request_content, bytes):
            content = request_content.decode(self.request.charset)
        else:
            content = request_content

        request_data = {}
        try:
            request_data = json.loads(content)
        except ValueError as exc:
            errors.append({"name": None, "description": repr(exc)})

        validated_data = {}
        try:
            validated_data = self.schema.deserialize(request_data)
        except colander.Invalid as exc:
            errors.append({"name": None, "description": exc.asdict()})

        if request_content and errors:
            raise self.prepare_exception(ParseError())

        return (validated_data, errors)

    def __call__(self):
        """Execute the view and return a response."""
        api_key = None
        api_key_text = self.parse_apikey()
        skip_check = False

        if api_key_text is None:
            self.log_count("none")
            if self.error_on_invalidkey:
                raise self.prepare_exception(InvalidAPIKey())

        if api_key_text is not None:
            try:
                api_key = get_key(self.request.db_session, api_key_text)
            except Exception:
                # if we cannot connect to backend DB, skip api key check
                skip_check = True
                self.raven_client.captureException()

        if api_key is not None and api_key.allowed(self.view_type):
            valid_key = api_key.valid_key
            self.log_count(valid_key)

            # Potentially avoid overhead of Redis connection.
            if self.ip_log_and_rate_limit:
                if self.log_ip_and_rate_limited(valid_key, api_key.maxreq):
                    raise self.prepare_exception(DailyLimitExceeded())

        elif skip_check:
            pass
        else:
            if api_key_text is not None:
                self.log_count("invalid")
            if self.error_on_invalidkey:
                raise self.prepare_exception(InvalidAPIKey())

        # If we failed to look up an ApiKey, create an empty one
        # rather than passing None through
        if api_key is None:
            api_key = Key()
        return self.view(api_key)
