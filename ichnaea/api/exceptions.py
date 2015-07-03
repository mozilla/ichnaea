from pyramid.httpexceptions import (
    HTTPClientError,
    HTTPError,
)
from pyramid.response import Response

import simplejson as json
from ichnaea.exceptions import BaseJSONError

MSG_GZIP = 'Error decompressing gzip data stream.'


class JSONError(HTTPError, BaseJSONError):
    # BBB: Old style error response for v1 API's

    def __init__(self, errors, status=400):
        body = {'errors': errors}
        Response.__init__(self, json.dumps(body))
        self.status = status
        self.content_type = 'application/json'


class BaseAPIError(HTTPClientError, BaseJSONError):

    code = 400
    domain = ''
    reason = ''
    message = ''

    def __init__(self):
        # explicitly avoid calling the HTTPException init magic
        Response.__init__(self, status=self.code, json_body=self.json_body())
        Exception.__init__(self)
        self.detail = self.message

    def __str__(self):
        return '<%s>: %s' % (self.__class__.__name__, self.code)

    @classmethod
    def json_body(cls):
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


class DailyLimitExceeded(BaseAPIError):

    code = 403
    domain = 'usageLimits'
    reason = 'dailyLimitExceeded'
    message = 'You have exceeded your daily limit.'


class InvalidAPIKey(BaseAPIError):

    code = 400
    domain = 'usageLimits'
    reason = 'keyInvalid'
    message = 'Missing or invalid API key.'


class LocationNotFound(BaseAPIError):

    code = 404
    domain = 'geolocation'
    reason = 'notFound'
    message = 'Not found'


class ParseError(BaseAPIError):

    code = 400
    domain = 'global'
    reason = 'parseError'
    message = 'Parse Error'

    def __init__(self, errors):
        # BBB: compatibility with JSONError
        BaseAPIError.__init__(self)
