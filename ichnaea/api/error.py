from pyramid.httpexceptions import HTTPError
from pyramid.response import Response

import simplejson as json
from ichnaea.exceptions import BaseJSONError

MSG_EMPTY = 'No JSON body was provided.'
MSG_GZIP = 'Error decompressing gzip data stream.'

DAILY_LIMIT = json.dumps({
    'error': {
        'errors': [{
            'domain': 'usageLimits',
            'reason': 'dailyLimitExceeded',
            'message': 'You have exceeded your daily limit.',
        }],
        'code': 403,
        'message': 'You have exceeded your daily limit.',
    }
})


class JSONError(HTTPError, BaseJSONError):
    def __init__(self, errors, status=400):
        body = {'errors': errors}
        Response.__init__(self, json.dumps(body))
        self.status = status
        self.content_type = 'application/json'

PARSE_ERROR = {'error': {
    'errors': [{
        'domain': 'global',
        'reason':
        'parseError',
        'message':
        'Parse Error',
    }],
    'code': 400,
    'message': 'Parse Error',
}}

PARSE_ERROR = json.dumps(PARSE_ERROR)


class JSONParseError(HTTPError, BaseJSONError):
    def __init__(self, errors, status=400):
        Response.__init__(self, PARSE_ERROR)
        self.status = status
        self.content_type = 'application/json'
