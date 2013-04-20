from cornice import Service
from pyramid.httpexceptions import HTTPError, HTTPNoContent
from pyramid.response import Response
from statsd import StatsdTimer

from ichnaea.db import Cell
from ichnaea.renderer import dump_decimal_json
from ichnaea.renderer import quantize
from ichnaea.schema import SearchSchema, MeasureSchema


class _JSONError(HTTPError):
    def __init__(self, errors, status=400):
        body = {'errors': errors}
        Response.__init__(self, dump_decimal_json(body))
        self.status = status
        self.content_type = 'application/json'


def error_handler(errors):
    return _JSONError(errors, errors.status)


MSG_CELL_OR_WIFI = 'You need to provide at least one cell or wifi entry.'


def cell_or_wifi(request):
    data = request.validated
    cell = data.get('cell', ())
    wifi = data.get('wifi', ())
    if not (any(cell) or any(wifi)):
        request.errors.add('body', 'body', MSG_CELL_OR_WIFI)


location_search = Service(
    name='location_search',
    path='/v1/search',
    description="Search for your current location.",
)


@location_search.post(renderer='json', accept="application/json",
                      schema=SearchSchema, error_handler=error_handler,
                      validators=cell_or_wifi)
def location_search_post(request):
    """
    Determine the current location based on provided data about
    nearby cell towers or wifi base stations.

    The request body is a nested JSON mapping, for example:

    .. code-block:: javascript

        {
            "cell": [
                {
                    "mcc": 724,
                    "mnc": 5,
                    "lac": 31421,
                    "cid": 60420242,
                    "strength": 57
                }
            ],
            "wifi": [
                {
                    "bssid": "02:8E:F2:62:EC:A4",
                    "strength": 42
                }
            ]
        }

    The mapping can contain zero to many entries per category. At least for one
    category an entry has to be provided. Empty categories can be omitted
    entirely.

    The strength should be an integer in the range of 0 to 100, where 100 means
    perfect reception and lower numbers mean gradually worse reception.

    For `cell` entries, the `mcc`, `mnc` and `cid` keys are required.

    For `wifi` entires, the `bssid` key is required.

    A successful result will be:

    .. code-block:: javascript

        {
            "status": "ok",
            "lat": -22.753919,
            "lon": -43.437108,
            "accuracy": 1000
        }

    The latitude and longitude are numbers, with six decimal places of
    actual precision. The accuracy is an integer measured in meters.

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
    cell = data['cell'][0]
    mcc = cell['mcc']
    mnc = cell['mnc']
    lac = cell['lac']
    cid = cell['cid']

    session = request.db_session
    query = session.query(Cell).filter(Cell.mcc == mcc)
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


location_measurement = Service(
    name='location_measurement',
    path='/v1/location/{lat}/{lon}',
    description="Provide a measurement result for a location.",
)


@location_measurement.post(renderer='json', accept="application/json",
                           schema=MeasureSchema, error_handler=error_handler,
                           validators=cell_or_wifi)
def location_measurement_post(request):
    """
    Send back data about nearby cell towers and wifi base stations.

    :param lat: The latitude, as a string representation of a float
    :param lon: The longitude, as a string representation of a float

    An example request against URL::

        /v1/location/-22.753919/-43.437108

    with a body of:

    .. code-block:: javascript

        {
            "cell": [
                {
                    "mcc": 724,
                    "mnc": 5,
                    "lac": 31421,
                    "cid": 60420242,
                    "strength": 57
                }
            ],
            "wifi": [
                {
                    "bssid": "02:8E:F2:62:EC:A4",
                    "strength": 42
                }
            ]
        }

    On successful submission, you get a 204 status code back without any
    data in the body.

    If an error occurred, you get a 400 HTTP status code and a body of:

    .. code-block:: javascript

        {
            "errors": {}
        }

    The errors mapping contains detailed information about the errors.
    """
    data = request.validated
    data['cell'][0]
    # todo store cell data
    return HTTPNoContent()


heartbeat = Service(name='heartbeat', path='/__heartbeat__')


@heartbeat.get(renderer='json')
def get_heartbeat(request):
    return {'status': 'OK'}
