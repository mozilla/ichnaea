from statsd import StatsdTimer

from ichnaea.db import Cell, RADIO_TYPE
from ichnaea.decimaljson import quantize


def search_cell(session, data):
    radio = RADIO_TYPE.get(data['radio'], 0)
    cell = data['cell'][0]
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


def search_request(request):
    data = request.validated
    if not data['cell']:
        # we don't have any wifi entries yet
        return {'status': 'not_found'}

    session = request.celldb.session()

    with StatsdTimer('get_cell_location'):
        result = search_cell(session, data)

    if result is None:
        return {'status': 'not_found'}

    return {
        'status': 'ok',
        'lat': result['lat'],
        'lon': result['lon'],
        'accuracy': result['accuracy'],
    }
