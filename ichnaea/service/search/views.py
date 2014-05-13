from ichnaea.models import (
    Cell,
    normalized_wifi_key,
    normalized_cell_dict,
    RADIO_TYPE,
    Wifi,
    CELLID_LAC,
    to_degrees,
    to_cellkey,
    join_cellkey,
)
from ichnaea.decimaljson import (
    quantize,
)
from ichnaea.service.base import check_api_key
from ichnaea.service.error import (
    MSG_ONE_OF,
    preprocess_request,
)
from ichnaea.heka_logging import get_heka_client
from ichnaea.service.search.schema import SearchSchema
from ichnaea.geocalc import distance
from collections import namedtuple
import operator

# maximum distance when clustering wifis, in km (0.5 => 500m)
MAX_DIST = 0.5


# helper class used in searching
Network = namedtuple('Network', ['key', 'lat', 'lon', 'range'])


def configure_search(config):
    config.add_route('v1_search', '/v1/search')
    config.add_view(search_view, route_name='v1_search', renderer='json')


def estimate_accuracy(lat, lon, points, minimum):
    if len(points) == 1:
        accuracy = points[0].range
    else:
        # Terrible approximation, but hopefully better
        # than the old approximation, "worst-case range":
        # this one takes the maximum distance from location
        # to any of the provided points.
        accuracy = max([distance(to_degrees(lat),
                                 to_degrees(lon),
                                 to_degrees(p.lat),
                                 to_degrees(p.lon)) * 1000
                        for p in points])
    return max(accuracy, minimum)


def search_cell(session, data):
    radio = RADIO_TYPE.get(data['radio'], -1)
    cells = []
    for cell in data['cell']:
        cell = normalized_cell_dict(cell, default_radio=radio)
        if not cell:
            continue

        key = to_cellkey(cell)

        query = session.query(Cell.lat, Cell.lon, Cell.range).filter(
            *join_cellkey(Cell, key)).filter(
            Cell.lat.isnot(None)).filter(
            Cell.lon.isnot(None)
        )
        result = query.first()
        if result is not None:
            cells.append(Network(key, *result))

    if not cells:
        return

    cells = [Network(*c) for c in cells]
    length = len(cells)
    avg_lat = sum([c.lat for c in cells]) / length
    avg_lon = sum([c.lon for c in cells]) / length
    return {
        'lat': quantize(avg_lat),
        'lon': quantize(avg_lon),
        'accuracy': estimate_accuracy(avg_lat, avg_lon,
                                      cells, 10000),
    }


def search_cell_lac(session, data):
    radio = RADIO_TYPE.get(data['radio'], -1)
    lacs = []
    for cell in data['cell']:
        if cell['mcc'] < 1 or cell['mnc'] < 0 or \
           cell['lac'] < 0 or cell['cid'] < 0:
            # Skip over invalid values
            continue

        if cell.get('radio'):
            radio = RADIO_TYPE.get(cell['radio'], -1)

        query = session.query(Cell).filter(
            Cell.radio == radio).filter(
            Cell.mcc == cell['mcc']).filter(
            Cell.mnc == cell['mnc']).filter(
            Cell.lac == cell['lac']).filter(
            Cell.cid == CELLID_LAC).filter(
            Cell.lat.isnot(None)).filter(
            Cell.lon.isnot(None)
        )
        result = query.first()
        if result is not None:
            lacs.append(result)

    if not lacs:
        return None

    # take the smallest LAC of any the user is inside
    lac = sorted(lacs, key=operator.attrgetter('range'))[0]

    return {
        'lat': quantize(lac.lat),
        'lon': quantize(lac.lon),
        'accuracy': max(10000, lac.range),
    }


def search_wifi(session, data):

    # estimate signal strength at -100 dBm if none is provided,
    # which is worse than the 99th percentile of wifi dBms we
    # see in practice (-98).
    def signal_strength(w):
        if 'signal' in w:
            return int(w['signal'])
        else:
            return -100

    wifi_signals = dict([(normalized_wifi_key(w['key']),
                          signal_strength(w))
                         for w in data['wifi']])
    wifi_keys = set(wifi_signals.keys())

    if not any(wifi_keys):
        # no valid normalized keys
        return None
    if len(wifi_keys) < 3:
        # we didn't even get three keys, bail out
        return None
    query = session.query(Wifi.key, Wifi.lat, Wifi.lon, Wifi.range).filter(
        Wifi.key.in_(wifi_keys)).filter(
        Wifi.lat.isnot(None)).filter(
        Wifi.lon.isnot(None))
    wifis = query.all()
    if len(wifis) < 3:
        # we got fewer than three actual matches
        return None

    wifis = [Network(normalized_wifi_key(w[0]), w[1], w[2], w[3])
             for w in wifis]

    # sort networks by signal strengths in query
    wifis.sort(lambda a, b: cmp(wifi_signals[b.key],
                                wifi_signals[a.key]))

    clusters = []

    for w in wifis:
        # try to assign w to a cluster (but at most one)
        for c in clusters:
            for n in c:
                if distance(quantize(n.lat), quantize(n.lon),
                            quantize(w.lat), quantize(w.lon)) <= MAX_DIST:
                    c.append(w)
                    w = None
                    break

            if len(c) >= 3:
                # if we have a cluster with more than 3
                # networks in it, return its centroid.
                length = len(c)
                avg_lat = sum([n.lat for n in c]) / length
                avg_lon = sum([n.lon for n in c]) / length
                return {
                    'lat': quantize(avg_lat),
                    'lon': quantize(avg_lon),
                    'accuracy': estimate_accuracy(avg_lat, avg_lon,
                                                  c, 100),
                }

            if w is None:
                break

        # if w didn't adhere to any cluster, make a new one
        if w is not None:
            clusters.append([w])

    # if we didn't get any clusters with >3 networks,
    # the query is a bunch of outliers; give up and
    # let the next location method try.
    return None


def search_geoip(geoip_db, client_addr):
    r = geoip_db.geoip_lookup(client_addr)

    if r is None:
        return None

    return {
        'lat': r['latitude'],
        'lon': r['longitude'],
        'accuracy': 40 * 1000
    }


def check_cell_or_wifi(data, errors):
    if errors:
        # don't add this error if something else was already wrong
        return

    cell = data.get('cell', ())
    wifi = data.get('wifi', ())
    if not any(wifi) and not any(cell):
        errors.append(dict(name='body', description=MSG_ONE_OF))


@check_api_key('search', True)
def search_view(request):
    heka_client = get_heka_client()

    data, errors = preprocess_request(
        request,
        schema=SearchSchema(),
        extra_checks=(check_cell_or_wifi, ),
    )

    session = request.db_slave_session
    result = None

    if data['wifi']:
        result = search_wifi(session, data)
        if result is not None:
            heka_client.incr('search.wifi_hit')
    if result is None:
        # no wifi result found, fall back to cell
        result = search_cell(session, data)
        if result is not None:
            heka_client.incr('search.cell_hit')
    if result is None:
        # no direct cell result found, try cell LAC
        result = search_cell_lac(session, data)
        if result is not None:
            heka_client.incr('search.cell_lac_hit')
    if result is None and request.client_addr:
        # no cell or wifi, fall back again to geoip
        result = search_geoip(request.registry.geoip_db,
                              request.client_addr)
        if result is not None:
            heka_client.incr('search.geoip_hit')

    if result is None:
        heka_client.incr('search.miss')
        return {'status': 'not_found'}

    return {
        'status': 'ok',
        'lat': result['lat'],
        'lon': result['lon'],
        'accuracy': result['accuracy'],
    }
