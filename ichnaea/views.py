from cornice import Service
import pyramid.httpexceptions as exc
from pyramid.response import Response
from statsd import StatsdTimer

from ichnaea.db import Cell


cell_location = Service(
    name='cell_location',
    path='/v1/cell/{mcc}/{mnc}/{lac}/{cid}',
    description="Get cell location information.",
    cors_policy={'origins': ('*',), 'credentials': True})


@cell_location.get()
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
        else:
            # work around float representation issues in Python 2.6
            return Response('{"lat": %s, "lon": %s, "accuracy": %s}' % (
                result.lat,
                result.lon,
                # TODO figure out actual meaning of `range`
                # we want to return accuracy in meters at 95% percentile
                20000,
            ))

heartbeat = Service(name='heartbeat', path='/__heartbeat__')


@heartbeat.get(renderer='json')
def get_heartbeat(request):
    return {'status': 'OK'}
