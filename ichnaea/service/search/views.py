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
    WIFI_MIN_ACCURACY,
    CELL_MIN_ACCURACY,
    LAC_MIN_ACCURACY,
    GEOIP_CITY_ACCURACY
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

# parameters for wifi clustering
MAX_WIFI_CLUSTER_KM = 0.5
MIN_WIFIS_IN_QUERY = 2
MIN_WIFIS_IN_CLUSTER = 2
MAX_WIFIS_IN_CLUSTER = 5


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

    length = len(cells)
    avg_lat = sum([c.lat for c in cells]) / length
    avg_lon = sum([c.lon for c in cells]) / length
    return {
        'lat': quantize(avg_lat),
        'lon': quantize(avg_lon),
        'accuracy': estimate_accuracy(avg_lat, avg_lon,
                                      cells, CELL_MIN_ACCURACY),
    }


def search_cell_lac(session, data):
    radio = RADIO_TYPE.get(data['radio'], -1)
    lacs = []
    for cell in data['cell']:
        cell = normalized_cell_dict(cell, default_radio=radio)
        if not cell:
            continue

        cell['cid'] = CELLID_LAC
        key = to_cellkey(cell)

        query = session.query(Cell.lat, Cell.lon, Cell.range).filter(
            *join_cellkey(Cell, key)).filter(
            Cell.lat.isnot(None)).filter(
            Cell.lon.isnot(None)
        )
        result = query.first()
        if result is not None:
            lacs.append(Network(key, *result))

    if not lacs:
        return

    # take the smallest LAC of any the user is inside
    lac = sorted(lacs, key=operator.attrgetter('range'))[0]

    return {
        'lat': quantize(lac.lat),
        'lon': quantize(lac.lon),
        'accuracy': max(LAC_MIN_ACCURACY, lac.range),
    }


def search_wifi(session, data):

    # Estimate signal strength at -100 dBm if none is provided,
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
        # No valid normalized keys.
        return None
    if len(wifi_keys) < MIN_WIFIS_IN_QUERY:
        # We didn't get enough keys.
        return None
    query = session.query(Wifi.key, Wifi.lat, Wifi.lon, Wifi.range).filter(
        Wifi.key.in_(wifi_keys)).filter(
        Wifi.lat.isnot(None)).filter(
        Wifi.lon.isnot(None))
    wifis = query.all()
    if len(wifis) < MIN_WIFIS_IN_QUERY:
        # We didn't get enough matches.
        return None

    wifis = [Network(normalized_wifi_key(w[0]), w[1], w[2], w[3])
             for w in wifis]

    # Sort networks by signal strengths in query.
    wifis.sort(lambda a, b: cmp(wifi_signals[b.key],
                                wifi_signals[a.key]))

    clusters = []

    # The first loop forms a set of clusters by distance,
    # preferring the cluster with the stronger signal strength
    # if there's a tie.
    for w in wifis:

        # Try to assign w to a cluster (but at most one).
        for c in clusters:
            for n in c:
                if distance(quantize(n.lat),
                            quantize(n.lon),
                            quantize(w.lat),
                            quantize(w.lon)) <= MAX_WIFI_CLUSTER_KM:
                    c.append(w)
                    w = None
                    break

            if w is None:
                break

        # If w didn't adhere to any cluster, make a new one.
        if w is not None:
            clusters.append([w])

    # The second loop selects a cluster and estimates the position of that
    # cluster. The selected cluster is the one with the most points, larger
    # than MIN_WIFIS_IN_CLUSTER; its position is estimated taking up-to
    # MAX_WIFIS_IN_CLUSTER worth of points from the cluster, which is
    # pre-sorted in signal-strength order due to the way we built the
    # clusters.
    #
    # The reasoning here is that if we have >1 cluster at all, we probably
    # have some bad data -- likely an AP or set of APs associated with a
    # single antenna that moved -- since a user shouldn't be able to hear
    # multiple groups 500m apart.
    #
    # So we're trying to select a cluster that's most-likely good data,
    # which we assume to be the one with the most points in it.
    #
    # The reason we take a subset of those points when estimating location
    # is that we're doing a (non-weighted) centroid calculation, which is
    # itself unbalanced by distant elements. Even if we did a weighted
    # centroid here, using radio intensity as a proxy for distance has an
    # error that increases significantly with distance, so we'd have to
    # underweight pretty heavily.

    clusters = [c for c in clusters if len(c) > MIN_WIFIS_IN_CLUSTER]

    if len(clusters) == 0:
        return None

    clusters.sort(lambda a, b: cmp(len(b), len(a)))
    cluster = clusters[0]
    sample = cluster[:min(len(cluster), MAX_WIFIS_IN_CLUSTER)]
    length = len(sample)
    avg_lat = sum([n.lat for n in sample]) / length
    avg_lon = sum([n.lon for n in sample]) / length
    return {
        'lat': quantize(avg_lat),
        'lon': quantize(avg_lon),
        'accuracy': estimate_accuracy(avg_lat, avg_lon,
                                      sample, WIFI_MIN_ACCURACY),
    }


def search_geoip(geoip_db, client_addr):
    r = geoip_db.geoip_lookup(client_addr)

    if r is None:
        return None

    return {
        'lat': r['latitude'],
        'lon': r['longitude'],
        'accuracy': GEOIP_CITY_ACCURACY
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
        accept_empty=True,
    )

    session = request.db_slave_session
    result = None

    if data and data['wifi']:
        result = search_wifi(session, data)
        if result is not None:
            heka_client.incr('search.wifi_hit')
            heka_client.timer_send('search.accuracy.wifi',
                                   result['accuracy'])

    if result is None and data:
        # no wifi result found, fall back to cell
        result = search_cell(session, data)
        if result is not None:
            heka_client.incr('search.cell_hit')
            heka_client.timer_send('search.accuracy.cell',
                                   result['accuracy'])

    if result is None and data:
        # no direct cell result found, try cell LAC
        result = search_cell_lac(session, data)
        if result is not None:
            heka_client.incr('search.cell_lac_hit')
            heka_client.timer_send('search.accuracy.cell_lac',
                                   result['accuracy'])

    if result is None and request.client_addr:
        # no cell or wifi, fall back again to geoip
        result = search_geoip(request.registry.geoip_db,
                              request.client_addr)
        if result is not None:
            heka_client.incr('search.geoip_hit')
            heka_client.timer_send('search.accuracy.geoip',
                                   result['accuracy'])

    if result is None:
        heka_client.incr('search.miss')
        return {'status': 'not_found'}

    return {
        'status': 'ok',
        'lat': result['lat'],
        'lon': result['lon'],
        'accuracy': result['accuracy'],
    }
