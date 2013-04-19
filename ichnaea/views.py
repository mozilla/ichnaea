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


@location_search.post(renderer='decimaljson')
def location_search_post(request):
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
            raise exc.HTTPNotFound()

        return {'lat': quantize(result.lat),
                'lon': quantize(result.lon),
                # TODO figure out actual meaning of `range`
                # we want to return accuracy in meters at 95% percentile
                'accuracy': 20000
                }


cell_measurement = Service(
    name='cell_measurement',
    path='/v1/cell',
    description="Post cell location measurement.",
)


@cell_measurement.post(renderer='decimaljson', accept="application/json")
def post_cell_measurement(request):
    return {'status': 'success'}


heartbeat = Service(name='heartbeat', path='/__heartbeat__')


@heartbeat.get(renderer='json')
def get_heartbeat(request):
    return {'status': 'OK'}
