"""
HTTP API specific exceptions and responses.
"""

from pyramid.httpexceptions import HTTPException
from pyramid.response import Response

from ichnaea.exceptions import (
    BaseClientError,
    BaseServiceError,
)


class JSONException(HTTPException):
    """
    A base class for HTTP responses acting as exceptions and containing
    a JSON body.
    """

    code = 500  #:
    empty_body = False  #:
    message = ''  #:

    def __init__(self):
        # explicitly avoid calling the HTTPException init magic
        if not self.empty_body:
            Response.__init__(self, status=self.code,
                              json_body=self.json_body())
        else:
            Response.__init__(self, status=self.code)
        Exception.__init__(self)
        self.detail = self.message

        if self.empty_body:
            del self.content_type
            del self.content_length

    def __str__(self):
        return '<%s>: %s' % (self.__class__.__name__, self.code)

    @classmethod
    def json_body(cls):  # pragma: no cover
        """A JSON representation of this response."""
        return {}


class UploadSuccess(JSONException):

    code = 200  #:

    @classmethod
    def json_body(cls):
        """A JSON representation of this response."""
        return {}


class UploadSuccessV1(UploadSuccess):
    """
    A variant of :exc:`~ichnaea.api.exceptions.UploadSuccess` used
    in earlier version 1 HTTP APIs.
    """

    code = 204  #:
    empty_body = True  #:


class BaseAPIError(JSONException):
    """
    A base class representing API errors that all act as HTTP responses
    and have a similar JSON body.
    """

    code = 400  #:
    domain = ''  #:
    reason = ''  #:
    message = ''  #:

    @classmethod
    def json_body(cls):
        """A JSON representation of this response."""
        return {
            'error': {
                'errors': [{
                    'domain': cls.domain,
                    'reason': cls.reason,
                    'message': cls.message,
                }],
                'code': cls.code,
                'message': cls.message,
            },
        }


class BaseAPIClientError(BaseAPIError, BaseClientError):
    """
    A base class for all errors that are the client's fault.
    """

    code = 400  #:
    domain = 'global'  #:
    reason = 'badRequest'  #:
    message = 'Bad Request'  #:


class BaseAPIServiceError(BaseAPIError, BaseServiceError):
    """
    A base class for all errors that are the service's fault.
    """

    code = 500  #:
    domain = 'global'  #:
    reason = 'internalError'  #:
    message = 'Internal Error'  #:


class DailyLimitExceeded(BaseAPIClientError):

    code = 403  #:
    domain = 'usageLimits'  #:
    reason = 'dailyLimitExceeded'  #:
    message = 'You have exceeded your daily limit.'  #:


class InvalidAPIKey(BaseAPIClientError):

    code = 400  #:
    domain = 'usageLimits'  #:
    reason = 'keyInvalid'  #:
    message = 'Missing or invalid API key.'  #:


class LocationNotFound(BaseAPIClientError):

    code = 404  #:
    domain = 'geolocation'  #:
    reason = 'notFound'  #:
    message = 'Not found'  #:


class LocationNotFoundV1(LocationNotFound):
    """
    A variant of :exc:`~ichnaea.api.exceptions.LocationNotFound` used
    in earlier version 1 HTTP APIs.
    """

    code = 200  #:

    @classmethod
    def json_body(cls):
        """A JSON representation of this response."""
        return {'status': 'not_found'}


class RegionNotFoundV0(LocationNotFound):
    """
    A variant of :exc:`~ichnaea.api.exceptions.LocationNotFound` used
    in earlier version 0 HTTP region APIs.
    """

    @classmethod
    def json_body(cls):
        """A JSON representation of this response."""
        return None


class RegionNotFoundV0JS(LocationNotFound):
    """
    A variant of :exc:`~ichnaea.api.exceptions.LocationNotFound` used
    in earlier version 0 HTTP region APIs.
    """

    def __init__(self):
        super(RegionNotFoundV0JS, self).__init__()
        self.content_length = 0
        self.content_type = 'text/javascript; charset=UTF-8'
        self.text = u''

    empty_body = True  #:


class ParseError(BaseAPIClientError):

    code = 400  #:
    domain = 'global'  #:
    reason = 'parseError'  #:
    message = 'Parse Error'  #:


class ServiceUnavailable(BaseAPIServiceError):

    code = 503  #:
    domain = 'global'  #:
    reason = 'serviceUnavailable'  #:
    message = 'Service Unavailable'  #:
