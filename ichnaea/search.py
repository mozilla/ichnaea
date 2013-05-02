from statsd import StatsdTimer

from ichnaea.db import Cell, RADIO_TYPE
from ichnaea.decimaljson import quantize


def search_request(request):
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
