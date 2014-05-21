from ichnaea.exceptions import BaseJSONError
from pyramid.httpexceptions import HTTPError
from ichnaea.decimaljson import dumps
from pyramid.response import Response

PARSE_ERROR = {
    "error": {
        "errors": [{
            "domain": "global",
            "reason": "parseError",
            "message": "Parse Error",
        }],
        "code": 400,
        "message": "Parse Error"
    }
}
PARSE_ERROR = dumps(PARSE_ERROR)


class JSONError(HTTPError, BaseJSONError):
    def __init__(self, errors, status=400):
        Response.__init__(self, PARSE_ERROR)
        self.status = status
        self.content_type = 'application/json'
