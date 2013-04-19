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


@location_search.post(renderer='decimaljson', accept="application/json")
def location_search_post(request):
    """
    Determine the current location based on provided data about
    nearby cell towers or wifi base stations.
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
            raise exc.HTTPNotFound()

        return {'lat': quantize(result.lat),
                'lon': quantize(result.lon),
                # TODO figure out actual meaning of `range`
                # we want to return accuracy in meters at 95% percentile
                'accuracy': 20000
                }


location_measurement = Service(
    name='location_measurement',
    path='/v1/location/{lat}/{lon}',
    description="Provide a measurement result for a location.",
)


@location_measurement.post(renderer='decimaljson', accept="application/json")
def location_measurement_post(request):
    return {'status': 'success'}


heartbeat = Service(name='heartbeat', path='/__heartbeat__')


@heartbeat.get(renderer='json')
def get_heartbeat(request):
    return {'status': 'OK'}
