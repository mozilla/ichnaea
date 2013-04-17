from cornice import Service
from statsd import StatsdTimer

from ichnaea.db import Cell


cell_location = Service(
    name='cell_location',
    path='/v1/cell',
    description="Get cell location information.",
    cors_policy={'origins': ('*',), 'credentials': True})


@cell_location.get(renderer='json')
def get_cell_location(request):
    # TODO validation
    mcc = int(request.GET['mcc'])
    mnc = int(request.GET['mnc'])
    lac = int(request.GET.get('lac', -1))
    cid = int(request.GET.get('cid', -1))

    session = request.db_session
    query = session.query(Cell).filter(Cell.mcc == mcc).filter(Cell.mnc == mnc)

    if lac >= 0:
        query.filter(Cell.lac == lac)
    if cid >= 0:
        query.filter(Cell.cid == cid)

    with StatsdTimer('get_cell_location'):
        result = query.first()
        if result is None:
            # TODO raise error
            return {
                'latitude': 0,
                'longitude': 0,
                'accuracy': 0,
            }
        else:
            return {
                'latitude': str(result.lat),
                'longitude': str(result.lon),
                # TODO figure out actual meaning of `range`
                # we want to return accuracy in meters at 95% percentile
                'accuracy': result.range,
            }

heartbeat = Service(name='heartbeat', path='/__heartbeat__')


@heartbeat.get(renderer='json')
def get_heartbeat(request):
    return {'status': 'OK'}
