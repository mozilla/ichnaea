from cornice import Service

from ichnaea.db import (
    Cell,
    normalize_wifi_key,
    RADIO_TYPE,
    Wifi,
)
from ichnaea.decimaljson import quantize
from ichnaea.schema import SearchSchema
from ichnaea.service.error import (
    error_handler,
    MSG_ONE_OF,
)


def configure_search(config):
    config.scan('ichnaea.service.search.views')


def search_cell(session, data):
    radio = RADIO_TYPE.get(data['radio'], -1)
    cell = data['cell'][0]
    if cell.get('radio'):
        radio = RADIO_TYPE.get(cell['radio'], -1)
    mcc = cell['mcc']
    mnc = cell['mnc']
    lac = cell['lac']
    cid = cell['cid']

    query = session.query(Cell)
    query = query.filter(Cell.radio == radio)
    query = query.filter(Cell.mcc == mcc)
    query = query.filter(Cell.mnc == mnc)
    query = query.filter(Cell.cid == cid)

    if lac >= 0:
        query = query.filter(Cell.lac == lac)

    result = query.first()
    if result is None:
        return

    return {
        'lat': quantize(result.lat),
        'lon': quantize(result.lon),
        'accuracy': 35000,
    }


def search_wifi(session, data):
    wifi_data = data['wifi']
    wifi_keys = set([normalize_wifi_key(w['key']) for w in wifi_data])
    if not wifi_keys:
        return None
    sql_null = None  # avoid pep8 warning
    query = session.query(Wifi.lat, Wifi.lon).filter(
        Wifi.key.in_(wifi_keys)).filter(
        Wifi.lat != sql_null).filter(
        Wifi.lon != sql_null)
    wifis = query.all()
    if len(wifis) < 2:
        return None
    length = len(wifis)
    avg_lat = sum([w[0] for w in wifis]) / length
    avg_lon = sum([w[1] for w in wifis]) / length
    return {
        'lat': quantize(avg_lat),
        'lon': quantize(avg_lon),
        'accuracy': 500,
    }


def search_request(request):
    data = request.validated
    session = request.db_slave_session

    result = None
    if data['wifi']:
        result = search_wifi(session, data)
    else:
        result = search_cell(session, data)
    if result is None:
        return {'status': 'not_found'}

    return {
        'status': 'ok',
        'lat': result['lat'],
        'lon': result['lon'],
        'accuracy': result['accuracy'],
    }


def check_cell_or_wifi(data, request):
    cell = data.get('cell', ())
    wifi = data.get('wifi', ())
    if not any(wifi) and not any(cell):
        request.errors.add('body', 'body', MSG_ONE_OF)


def search_validator(request):
    if len(request.errors):
        return
    check_cell_or_wifi(request.validated, request)


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
                    "radio": "umts",
                    "mcc": 123,
                    "mnc": 123,
                    "lac": 12345,
                    "cid": 12345,
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

    The top-level radio type must be one of "gsm", "cdma" or be omitted (for
    example for tablets or laptops without a cell radio).

    The cell specific radio entry must be one of "gsm", "cdma", "umts" or
    "lte".

    See :ref:`cell_records` for a detailed explanation of the cell record
    fields for the different network standards.

    For `wifi` entries, the `key` field is required. The client must check the
    Wifi SSID for a `_nomap` suffix. Wifi's with such a suffix must not be
    submitted to the server. Wifi's with a hidden SSID should not be submitted
    to the server either.

    The `key` is a the BSSID or MAC address of the wifi network. So for example
    a valid key would look similar to `01:23:45:67:89:ab`.

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
