import logging

from cornice import Service
from pyramid.httpexceptions import HTTPError, HTTPNoContent
from pyramid.response import Response

from ichnaea.decimaljson import dumps
from ichnaea.schema import SubmitSchema
from ichnaea.service.submit.submit import submit_request

logger = logging.getLogger('ichnaea')


def configure_submit(config):
    config.scan('ichnaea.service.submit.views')


class _JSONError(HTTPError):
    def __init__(self, errors, status=400):
        body = {'errors': errors}
        Response.__init__(self, dumps(body))
        self.status = status
        self.content_type = 'application/json'


def error_handler(errors):
    logger.debug('error_handler' + repr(errors))
    return _JSONError(errors, errors.status)


MSG_ONE_OF = 'You need to provide a mapping with least one cell or wifi entry.'


def check_cell_or_wifi(data, request):
    cell = data.get('cell', ())
    wifi = data.get('wifi', ())
    if not any(wifi) and not any(cell):
        request.errors.add('body', 'body', MSG_ONE_OF)


def submit_validator(request):
    if len(request.errors):
        return
    for item in request.validated['items']:
        if not check_cell_or_wifi(item, request):
            # quit on first Error
            return


submit = Service(
    name='submit',
    path='/v1/submit',
    description="Submit a measurement result for a location.",
)


@submit.post(renderer='json', accept="application/json",
             schema=SubmitSchema, error_handler=error_handler,
             validators=submit_validator)
def submit_post(request):
    """
    Submit data about nearby cell towers and wifi base stations.

    An example request against URL::

        /v1/submit

    with a body of items:

    .. code-block:: javascript

        {'items': [
           {
            "lat": -22.7539192,
            "lon": -43.4371081,
            "time": "2012-03-15T11:12:13.456Z",
            "accuracy": 10,
            "altitude": 100,
            "altitude_accuracy": 1,
            "radio": "gsm",
            "cell": [
                {
                    "radio": "umts",
                    "mcc": 123,
                    "mnc": 123,
                    "lac": 12345,
                    "cid": 12345,
                    "signal": -60
                }
            ],
            "wifi": [
                {
                    "key": "3680873e9b83738eb72946d19e971e023e51fd01",
                    "channel": 11,
                    "frequency": 2412,
                    "signal": -50
                }
            ]
           }
           ]
        }

    The fields have the same meaning as explained in the search API.

    The only required fields are `lat` and `lon` and at least one cell or wifi
    entry.

    The altitude, accuracy and altitude_accuracy fields are all measured in
    meters. Altitude measures the height above or below the mean sea level,
    as defined by WGS 84.

    The timestamp has to be in UTC time, encoded in ISO 8601. If not
    provided, the server time will be used.

    On successful submission, you get a 204 status code back without any
    data in the body.

    If an error occurred, you get a 400 HTTP status code and a body of:

    .. code-block:: javascript

        {
            "errors": {}
        }

    The errors mapping contains detailed information about the errors.
    """
    submit_request(request)
    return HTTPNoContent()
