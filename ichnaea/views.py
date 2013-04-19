from decimal import Decimal
from cornice import Service
import pyramid.httpexceptions as exc
from statsd import StatsdTimer

from ichnaea.db import Cell

MILLION = Decimal(1000000)


location_search = Service(
    name='location_search',
    path='/v1/search',
    description="Search for your current location.",
)


def quantize(value):
    return (Decimal(value) / MILLION).quantize(Decimal('1.000000'))


@location_search.post(renderer='json', accept="application/json")
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
            ]
            "wifi": [
                {
                    "bssid": "02:8E:F2:62:EC:A4",
                    "ssid": "my network",
                    "strength": 42
                }
            ]
        }

    The mapping can contain zero to many entries per category. At least for one
    category an entry has to be provided.

    The strength should be an integer in the range of 0 to 100, where 100 means
    perfect reception and lower numbers mean gradually worse reception.

    For `cell` entries, the `strength` and `lac` keys are optional.

    For `wifi` entires, only the `bssid` field is required.

    A successful result will be:

    .. code-block:: javascript

        {
            "status": "ok",
            "lat": -22.753919,
            "lon": -43.437108,
            "accuracy": 20000
        }

    The latitude and longitude are numbers, with at most six decimal digits of
    precision. The accuracy is an integer measured in meters.

    If no position can be determined, you instead get:

    .. code-block:: javascript

        {
            "status": "not_found"
        }

    If the request couldn't be processed or a validation error occurred, you
    get a HTTP status code of 400 and a JSON body:

    .. code-block:: javascript

        {
            "status": "error",
            "errors": {}
        }

    The errors mapping contains detailed information about the errors.
    """

    data = request.json
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


@location_measurement.post(renderer='json', accept="application/json")
def location_measurement_post(request):
    """
    Send back data about nearby cell towers and wifi base stations.

    :param lat: The latitude, as a string representation of a float
    :param lon: The longitude, as a string representation of a float

    An example request is::

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
            ]
            "wifi": [
                {
                    "bssid": "02:8E:F2:62:EC:A4",
                    "ssid": "my network",
                    "strength": 42
                }
            ]
        }

    A successful result will be:

    .. code-block:: javascript

        {
            "status": "ok",
        }

    If an error occurred, you get a 400 HTTP status code and a body of:

    .. code-block:: javascript

        {
            "status": "error",
            "errors": {}
        }

    The errors mapping contains detailed information about the errors.
    """

    return {'status': 'ok'}


heartbeat = Service(name='heartbeat', path='/__heartbeat__')


@heartbeat.get(renderer='json')
def get_heartbeat(request):
    return {'status': 'OK'}
