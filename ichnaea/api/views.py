"""
Implementation of a API specific HTTP service view.
"""

import json
from hashlib import sha512

import colander
from ipaddress import ip_address
import markus
from pymysql.err import DatabaseError
from redis import RedisError
from sqlalchemy.exc import DBAPIError
from structlog.threadlocal import bind_threadlocal

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
    cors_origin = "*"  # Allow all CORS origins for API views
    cors_max_age = 86400 * 30  # Cache preflight requests for 30 days.

    def __init__(self, request):
        super(BaseAPIView, self).__init__(request)
        self.raven_client = request.registry.raven_client
        self.redis_client = request.registry.redis_client

    def parse_apikey(self):
        try:
            api_key_text = self.request.GET.get("key", None)
        except Exception:
            api_key_text = None
        if api_key_text:
            # Validate key and potentially return None
            valid_key = validated_key(api_key_text)
            if valid_key is None:
                bind_threadlocal(invalid_api_key=api_key_text)
            return valid_key
        return None

    def log_count(self, valid_key):
        METRICS.incr(
            self.view_type + ".request",
            tags=["path:" + self.metric_path, "key:" + valid_key],
        )
        bind_threadlocal(
            api_key=valid_key, api_path=self.metric_path, api_type=self.view_type
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
                new_ip, _, limit_count, _ = pipe.execute()
            log_params = {
                "api_key_count": limit_count,
                "api_key_repeat_ip": new_ip == 0,
            }
            if maxreq:
                should_limit = limit_count > maxreq
                log_params["rate_quota"] = maxreq
                log_params["rate_remaining"] = max(0, maxreq - limit_count)
                log_params["rate_allowed"] = not should_limit
            bind_threadlocal(**log_params)
        except RedisError:
            self.raven_client.captureException()

        return should_limit

    def preprocess_request(self):

        request_content = self.request.body
        if self.request.headers.get("Content-Encoding") == "gzip":
            # handle gzip self.request bodies
            try:
                request_content = util.decode_gzip(self.request.body)
            except GZIPDecodeError as exc:
                raise self.prepare_exception(ParseError({"decode": repr(exc)}))

        try:
            content = request_content.decode(self.request.charset)
        except UnicodeDecodeError as exc:
            # Use str(), since repr() includes the full source bytes
            raise self.prepare_exception(ParseError({"decode": str(exc)}))

        request_data = {}
        if content:
            try:
                request_data = json.loads(content)
            except ValueError as exc:
                raise self.prepare_exception(ParseError({"decode": repr(exc)}))

        validated_data = {}
        errors = None
        try:
            validated_data = self.schema.deserialize(request_data)
        except colander.Invalid as exc:
            errors = {"validation": exc.asdict()}

        if request_content and errors:
            raise self.prepare_exception(ParseError(errors))

        if self.ip_log_and_rate_limit and validated_data and not errors:
            # Count unique daily requests

            def superflatten(data):
                """Sort lists of dicts in request data."""
                if isinstance(data, dict):
                    return repr(
                        sorted([(key, superflatten(val)) for key, val in data.items()])
                    )
                if isinstance(data, (list, tuple)):
                    return repr(sorted([superflatten(item) for item in data]))
                return repr(data)

            valid_data = self.schema.serialize(validated_data)
            flatter_data = superflatten(valid_data)
            valid_content = json.dumps(flatter_data, sort_keys=True)
            siggen = sha512(valid_content.encode())
            client_addr = self.request.client_addr or "127.0.0.1"
            siggen.update(client_addr.encode())
            siggen.update(self.request.url.encode())  # Includes the API key if given
            signature = siggen.hexdigest()
            today = util.utcnow().date().isoformat()
            key = f"apirequest:{today}"
            with self.redis_client.pipeline() as pipe:
                pipe.pfadd(key, signature)
                pipe.expire(key, 90000)  # 25 hours
                new_request, _ = pipe.execute()
            bind_threadlocal(
                api_repeat_request=not new_request, api_request_sig=signature[:8]
            )

        return validated_data

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
            except (DatabaseError, DBAPIError):
                # if we cannot connect to backend DB, skip api key check
                skip_check = True
                self.raven_client.captureException()
                bind_threadlocal(
                    api_key=api_key_text,
                    api_path=self.metric_path,
                    api_type=self.view_type,
                    api_key_db_fail=True,
                )

        if api_key is not None:
            valid_key = api_key.valid_key
            if api_key.allowed(self.view_type):
                self.log_count(valid_key)

                # Potentially avoid overhead of Redis connection.
                if self.ip_log_and_rate_limit:
                    if self.log_ip_and_rate_limited(valid_key, api_key.maxreq):
                        raise self.prepare_exception(DailyLimitExceeded())
            else:
                self.log_count("invalid")
                # Switch "invalid" with real key, add "api_key_allowed"
                bind_threadlocal(api_key=valid_key, api_key_allowed=False)

                if self.error_on_invalidkey:
                    raise self.prepare_exception(InvalidAPIKey())

        elif skip_check:
            pass
        else:
            if api_key_text is not None:
                self.log_count("invalid")
                bind_threadlocal(invalid_api_key=api_key_text)
            if self.error_on_invalidkey:
                raise self.prepare_exception(InvalidAPIKey())

        # If we failed to look up an ApiKey, create an empty one
        # rather than passing None through
        if api_key is None:
            api_key = Key()
        return self.view(api_key)
