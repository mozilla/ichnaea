from colander import Invalid
from pyramid.httpexceptions import HTTPError
from pyramid.response import Response

from ichnaea.decimaljson import (
    dumps,
    loads,
)
from ichnaea.exceptions import BaseJSONError

MSG_ONE_OF = 'You need to provide a mapping with least one cell or wifi entry.'


class JSONError(HTTPError, BaseJSONError):
    def __init__(self, errors, status=400):
        body = {'errors': errors}
        Response.__init__(self, dumps(body))
        self.status = status
        self.content_type = 'application/json'


def preprocess_request(request, schema, extra_checks=(), response=JSONError):
    body = {}
    errors = []
    validated = {}

    if request.body:
        try:
            body = loads(request.body, encoding=request.charset)
        except ValueError as e:
            errors.append(dict(name=None, description=e.message))

    if errors and response is not None:
        # the response / None check is used in schema tests
        # if we couldn't decode the JSON body, just return
        raise response(errors)

    # schema validation, but report at most one error at a time
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

    for func in extra_checks:
        func(validated, errors)

    if errors and response is not None:
        # the response / None check is used in schema tests
        request.registry.heka_client.debug('error_handler' + repr(errors))
        raise response(errors)

    return (validated, errors)
