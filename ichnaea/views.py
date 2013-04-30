from cornice import Service
from pyramid.httpexceptions import HTTPError, HTTPNoContent
from pyramid.response import Response
from statsd import StatsdTimer

from ichnaea.db import Cell, RADIO_TYPE
from ichnaea.decimaljson import dumps, quantize
from ichnaea.schema import SearchSchema, SubmitSchema
from ichnaea.worker import add_measures


class _JSONError(HTTPError):
    def __init__(self, errors, status=400):
        body = {'errors': errors}
        Response.__init__(self, dumps(body))
        self.status = status
        self.content_type = 'application/json'


def error_handler(errors):
    return _JSONError(errors, errors.status)


MSG_ONE_OF = 'You need to provide a mapping with least one cell or wifi entry.'
MSG_TWO_WIFI = 'You need to specify at least two wifi entries.'


def check_cell_or_wifi(data, request):
    cell = data.get('cell', ())
    wifi = data.get('wifi', ())
    if not any(wifi):
        if not any(cell):
            request.errors.add('body', 'body', MSG_ONE_OF)
    elif len(wifi) < 2:
        request.errors.add('body', 'body', MSG_TWO_WIFI)


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
                    "signal": -60
                }
            ],
            "wifi": [
                {
                    "mac": "01:23:45:67:89:AB",
                    "channel": 11,
                    "frequency": 2412,
                    "noise": 40,
                    "signal": -50
                },
                {
                    "mac": "01:23:45:67:AB:12"
                }
            ]
        }

    The mapping can contain zero to many entries per category. At least for one
    category an entry has to be provided. Empty categories can be omitted
    entirely.

    The radio entry must be one of "gsm" or "cdma".

    For `cell` entries, the `mcc`, `mnc` and `cid` keys are required.

    For `wifi` entries, the `mac` key is required. If any wifi lookup is made,
    at least two entries need to be provided.

    The signal is the signal strength measured in dBm, the noise is the
    signal to noise ratio measured in dB. The frequency is measured in MHz.

    In a CDMA network, the system id (sid) should be sent in the mnc field,
    the network id (nid) in the lac field and base station id (bid) in the
    cid field.

    A successful result will be:

    .. code-block:: javascript

        {
            "status": "ok",
            "lat": -22.753919,
            "lon": -43.437108,
            "accuracy": 1000
        }

    The latitude and longitude are numbers, with six decimal places of
    actual precision. The accuracy is an integer measured in meters and defines
    a circle around the given location.

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

    data = request.validated
    if not data['cell']:
        # we don't have any wifi entries yet
        return {
            'status': 'not_found',
        }

    radio = RADIO_TYPE.get(data['radio'], 0)
    cell = data['cell'][0]
    mcc = cell['mcc']
    mnc = cell['mnc']
    lac = cell['lac']
    cid = cell['cid']

    session = request.celldb.session()
    query = session.query(Cell)
    query = query.filter(Cell.radio == radio)
    query = query.filter(Cell.mcc == mcc)
    query = query.filter(Cell.mnc == mnc)
    query = query.filter(Cell.cid == cid)

    if lac >= 0:
        query = query.filter(Cell.lac == lac)

    with StatsdTimer('get_cell_location'):
        result = query.first()

        if result is None:
            return {
                'status': 'not_found',
            }

        return {
            'status': 'ok',
            'lat': quantize(result.lat),
            'lon': quantize(result.lon),
            'accuracy': 20000,
        }


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
            "lat": -22.753919,
            "lon": -43.437108,
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
                    "mac": "01:23:45:67:89:AB",
                    "channel": 11,
                    "frequency": 2412,
                    "noise": 40,
                    "signal": -50
                },
                {
                    "mac": "01:23:45:67:AB:12"
                }
            ]
           }
           ]
        }

    The fields have the same meaning as explained in the search API.

    The only required fields are `lat` and `lon` and at least one cell or wifi
    entry.

    The altitude, accuracy and altitude_accuracy fields are all measured in
    meters. Altitude measures the height above or below the mean sea level.

    On successful submission, you get a 204 status code back without any
    data in the body.

    If an error occurred, you get a 400 HTTP status code and a body of:

    .. code-block:: javascript

        {
            "errors": {}
        }

    The errors mapping contains detailed information about the errors.
    """
    add_measures(request)
    return HTTPNoContent()


heartbeat = Service(name='heartbeat', path='/__heartbeat__')


@heartbeat.get(renderer='json')
def get_heartbeat(request):
    return {'status': 'OK'}
