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
    sql_null = None  # avoid pep8 warning
    radio = RADIO_TYPE.get(data['radio'], -1)
    cells = []
    for cell in data['cell']:
        if cell['lac'] == -1 or cell['cid'] == -1:
            # Skip over invalid LAC and CID values
            continue
        if cell.get('radio'):
            radio = RADIO_TYPE.get(cell['radio'], -1)

        query = session.query(Cell.lat, Cell.lon).filter(
            Cell.radio == radio).filter(
            Cell.mcc == cell['mcc']).filter(
            Cell.mnc == cell['mnc']).filter(
            Cell.lac == cell['lac']).filter(
            Cell.cid == cell['cid']).filter(
            Cell.lac != -1).filter(
            Cell.cid != -1).filter(
            Cell.lat != sql_null).filter(
            Cell.lon != sql_null
        )
        result = query.first()
        if result is not None:
            cells.append(result)

    if not cells:
        return

    length = len(cells)
    avg_lat = sum([c[0] for c in cells]) / length
    avg_lon = sum([c[1] for c in cells]) / length
    return {
        'lat': quantize(avg_lat),
        'lon': quantize(avg_lon),
        'accuracy': 35000,
    }


def search_wifi(session, data):
    wifi_data = data['wifi']
    wifi_keys = set([normalize_wifi_key(w['key']) for w in wifi_data])
    if not any(wifi_keys):
        # no valid normalized keys
        return None
    if len(wifi_keys) < 2:
        # we didn't even get two keys, bail out
        return None
    sql_null = None  # avoid pep8 warning
    query = session.query(Wifi.lat, Wifi.lon).filter(
        Wifi.key.in_(wifi_keys)).filter(
        Wifi.lat != sql_null).filter(
        Wifi.lon != sql_null)
    wifis = query.all()
    if len(wifis) < 2:
        # we got fewer than two actual matches
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
    if result is None:
        # no wifi result found, fall back to cell
        result = search_cell(session, data)
    if result is None:
        return {'status': 'not_found'}

    return {
        'status': 'ok',
        'lat': result['lat'],
        'lon': result['lon'],
        'accuracy': result['accuracy'],
    }
