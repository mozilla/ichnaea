from cornice import Service
from pyramid.httpexceptions import HTTPError, HTTPNoContent
from pyramid.response import Response

from ichnaea.decimaljson import dumps
from ichnaea.schema import SearchSchema, SubmitSchema
from ichnaea.search import search_request
from ichnaea.submit import submit_request


class _JSONError(HTTPError):
    def __init__(self, errors, status=400):
        body = {'errors': errors}
        Response.__init__(self, dumps(body))
        self.status = status
        self.content_type = 'application/json'


def error_handler(errors):
    return _JSONError(errors, errors.status)


MSG_ONE_OF = 'You need to provide a mapping with least one cell or wifi entry.'


def check_cell_or_wifi(data, request):
    cell = data.get('cell', ())
    wifi = data.get('wifi', ())
    if not any(wifi) and not any(cell):
        request.errors.add('body', 'body', MSG_ONE_OF)


def search_validator(request):
    if len(request.errors):
        return
    check_cell_or_wifi(request.validated, request)


def submit_validator(request):
    if len(request.errors):
        return
    for item in request.validated['items']:
        if not check_cell_or_wifi(item, request):
            # quit on first Error
            return

search = Service(
    name='search',
    path='/v1/search',
    description="Search for your current location.",
)


@search.post(renderer='json', accept="application/json",
             schema=SearchSchema, error_handler=error_handler,
             validators=search_validator)
def search_post(request):
    """
    Determine the current location based on provided data about
    nearby cell towers or wifi base stations.

    The request body is a nested JSON mapping, for example:

    .. code-block:: javascript

        {
            "radio": "gsm",
            "cell": [
                {
                    "mcc": 724,
                    "mnc": 5,
                    "lac": 31421,
                    "cid": 60420242,
                    "signal": -61,
                    "asu": 26
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

    The mapping can contain zero to many entries per category. At least for one
    category an entry has to be provided. Empty categories can be omitted
    entirely.

    The radio entry must be one of "gsm", "cdma", "umts" or "lte".

    See :ref:`cell_records` for a detailed explanation of the cell record
    fields for the different network standards.

    For `wifi` entries, the `key` field is required. The client must check the
    Wifi SSID for a `_nomap` suffix. Wifi's with such a suffix must not be
    submitted to the server. Wifi's with a hidden SSID should not be submitted
    to the server either.

    The `key` is a SHA1 hash of the concatenated BSSID and SSID of the wifi
    network. So for example for a bssid of `01:23:45:67:89:ab` and a
    ssid of `network name`, the result should be:
    `3680873e9b83738eb72946d19e971e023e51fd01`. In Python this would be coded
    as:

    .. code-block:: python

        import hashlib

        bssid = '01:23:45:67:89:ab'.encode('utf-8')
        ssid = 'network name'.encode('utf-8')
        key = hashlib.sha1(bssid + ssid).hexdigest()

    A successful result will be:

    .. code-block:: javascript

        {
            "status": "ok",
            "lat": -22.7539192,
            "lon": -43.4371081,
            "accuracy": 1000
        }

    The latitude and longitude are numbers, with seven decimal places of
    actual precision. The coordinate reference system is WGS 84. The accuracy
    is an integer measured in meters and defines a circle around the location.

    If no position can be determined, you instead get:

    .. code-block:: javascript

        {
            "status": "not_found"
        }

    If the request couldn't be processed or a validation error occurred, you
    get a HTTP status code of 400 and a JSON body:

    .. code-block:: javascript

        {
            "errors": {}
        }

    The errors mapping contains detailed information about the errors.
    """
    return search_request(request)


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
                    "mcc": 724,
                    "mnc": 5,
                    "lac": 31421,
                    "cid": 60420242,
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


heartbeat = Service(name='heartbeat', path='/__heartbeat__')


@heartbeat.get(renderer='json')
def get_heartbeat(request):
    return {'status': 'OK'}
