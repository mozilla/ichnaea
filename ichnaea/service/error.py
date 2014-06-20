import zlib

from colander import Invalid
from ichnaea.exceptions import BaseJSONError
from pyramid.httpexceptions import HTTPError
from pyramid.response import Response

from ichnaea.customjson import (
    dumps,
    loads,
)

MSG_EMPTY = 'No JSON body was provided.'
MSG_GZIP = 'Error decompressing gzip data stream.'
MSG_ONE_OF = 'You need to provide a mapping with least one cell or wifi entry.'
MSG_BAD_RADIO = 'Radio fields were not consistent in the cellTower data.'


DAILY_LIMIT = dumps({
    "error": {
        "errors": [{
            "domain": "usageLimits",
            "reason": "dailyLimitExceeded",
            "message": "You have exceeded your daily limit.",
        }],
        "code": 403,
        "message": "You have exceeded your daily limit.",
    }
})


class JSONError(HTTPError, BaseJSONError):
    def __init__(self, errors, status=400):
        body = {'errors': errors}
        Response.__init__(self, dumps(body))
        self.status = status
        self.content_type = 'application/json'

PARSE_ERROR = {"error": {
    "errors": [{
        "domain": "global",
        "reason":
        "parseError",
        "message":
        "Parse Error",
    }],
    "code": 400,
    "message": "Parse Error"
}}

PARSE_ERROR = dumps(PARSE_ERROR)


class JSONParseError(HTTPError, BaseJSONError):
    def __init__(self, errors, status=400):
        Response.__init__(self, PARSE_ERROR)
        self.status = status
        self.content_type = 'application/json'


def preprocess_request(request, schema, extra_checks=(), response=JSONError,
                       accept_empty=False):
    body = {}
    errors = []
    validated = {}

    body = request.body
    if body:
        if request.headers.get('Content-Encoding') == 'gzip':
            # handle gzip request bodies
            try:
                body = zlib.decompress(body, 16 + zlib.MAX_WBITS)
            except zlib.error:
                errors.append(dict(name=None, description=MSG_GZIP))

        if not errors:
            try:
                body = loads(body, encoding=request.charset)
            except ValueError as e:
                errors.append(dict(name=None, description=e.message))
    else:
        errors.append(dict(name=None, description=MSG_EMPTY))

    if accept_empty and body == {}:
        return ({}, errors)

    if not body or (errors and response is not None):
        if response is not None:
            request.registry.heka_client.error('error_handler' + repr(errors))
            raise response(errors)

    # schema validation, but report at most one error at a time

    verify_schema(schema, body, errors, validated)

    for func in extra_checks:
        func(validated, errors)

    if errors and response is not None:
        # the response / None check is used in schema tests
        request.registry.heka_client.error('error_handler' + repr(errors))
        raise response(errors)

    return (validated, errors)


def verify_schema(schema, body, errors, validated):
    schema = schema.bind(request=body)
    for attr in schema.children:
        name = attr.name
        try:
            if name not in body:
                deserialized = attr.deserialize()
            else:
                deserialized = attr.deserialize(body[name])
        except Invalid as e:
            # the struct is invalid
            err_dict = e.asdict()
            try:
                errors.append(dict(name=name, description=err_dict[name]))
                break
            except KeyError:
                for k, v in err_dict.items():
                    if k.startswith(name):
                        errors.append(dict(name=k, description=v))
                        break
                break
        else:
            validated[name] = deserialized
