from decimal import Decimal
from cornice import Service
import pyramid.httpexceptions as exc
from statsd import StatsdTimer

from ichnaea.db import Cell

HUNDREDK = Decimal(100000)


cell_location = Service(
    name='cell_location',
    path='/v1/cell/{mcc}/{mnc}/{lac}/{cid}',
    description="Get cell location information.",
)


def quantize(value):
    return (Decimal(value) / HUNDREDK).quantize(Decimal('1.00000'))


@cell_location.get(renderer='decimaljson')
def get_cell_location(request):
    # TODO validation
    mcc = int(request.matchdict['mcc'])
    mnc = int(request.matchdict['mnc'])
    lac = int(request.matchdict['lac'])
    cid = int(request.matchdict['cid'])

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
