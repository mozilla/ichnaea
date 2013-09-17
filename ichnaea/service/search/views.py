from cornice import Service

from ichnaea.models import (
    Cell,
    normalize_wifi_key,
    RADIO_TYPE,
    Wifi,
)
from ichnaea.decimaljson import quantize
from ichnaea.service.error import (
    error_handler,
    MSG_ONE_OF,
)
from ichnaea.service.search.schema import SearchSchema


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
