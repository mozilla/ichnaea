from collections import namedtuple
import operator

import mobile_codes
from sqlalchemy.sql import and_, or_

from ichnaea.geocalc import (
    distance,
    location_is_in_country,
)
from ichnaea.geoip import radius_from_geoip
from ichnaea.heka_logging import get_heka_client, RAVEN_ERROR
from ichnaea.models import (
    Cell,
    normalized_wifi_key,
    normalized_cell_dict,
    RADIO_TYPE,
    Wifi,
    CELLID_LAC,
    to_cellkey,
    join_cellkey,
    WIFI_MIN_ACCURACY,
    CELL_MIN_ACCURACY,
    LAC_MIN_ACCURACY,
    DEGREE_DECIMAL_PLACES,
)
from ichnaea.service.base import check_api_key
from ichnaea.service.error import (
    MSG_ONE_OF,
    preprocess_request,
)
from ichnaea.service.search.schema import SearchSchema
from ichnaea.stats import get_stats_client


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
        accuracy = max([distance(lat, lon, p.lat, p.lon) * 1000
                        for p in points])
    if accuracy is not None:
        accuracy = round(float(accuracy), DEGREE_DECIMAL_PLACES)
    return max(accuracy, minimum)


def query_cell_networks(session, cell_keys):
    if not cell_keys:
        return []

    cell_filter = []
    for key in cell_keys:
        # create a list of 'and' criteria for cell keys
        criterion = join_cellkey(Cell, key)
        cell_filter.append(and_(*criterion))

    # Keep the cid to distinguish cell from lac later on
    query = session.query(Cell.cid, Cell.lat, Cell.lon, Cell.range).filter(
        or_(*cell_filter)).filter(
        Cell.lat.isnot(None)).filter(
        Cell.lon.isnot(None))

    cells = []
    for result in query.all():
        # The first entry is the key, used only to distinguish cell from lac
        cells.append(Network(*result))

    return cells


def search_cell(session, cells):
    if not cells:
        return

    length = len(cells)
    avg_lat = sum([c.lat for c in cells]) / length
    avg_lon = sum([c.lon for c in cells]) / length
    return {
        'lat': avg_lat,
        'lon': avg_lon,
        'accuracy': estimate_accuracy(avg_lat, avg_lon,
                                      cells, CELL_MIN_ACCURACY),
    }


def search_cell_lac(session, lacs):
    if not lacs:
        return

    # take the smallest LAC of any the user is inside
    lac = sorted(lacs, key=operator.attrgetter('range'))[0]
    accuracy = max(LAC_MIN_ACCURACY, lac.range)
    accuracy = round(float(accuracy), DEGREE_DECIMAL_PLACES)
    return {
        'lat': lac.lat,
        'lon': lac.lon,
        'accuracy': accuracy,
    }


def search_wifi(session, wifis):
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
                         for w in wifis])
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
                if distance(n.lat, n.lon,
                            w.lat, w.lon) <= MAX_WIFI_CLUSTER_KM:
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
        'lat': avg_lat,
        'lon': avg_lon,
        'accuracy': estimate_accuracy(avg_lat, avg_lon,
                                      sample, WIFI_MIN_ACCURACY),
    }


def check_cell_or_wifi(data, errors):
    if errors:
        # don't add this error if something else was already wrong
        return

    cell = data.get('cell', ())
    wifi = data.get('wifi', ())
    if not any(wifi) and not any(cell):
        errors.append(dict(name='body', description=MSG_ONE_OF))


def most_common(ls):
    """
    Return the most commonly-occurring element of an iterable, or
    None if the iterable is empty.
    """
    counts = {}
    for e in ls:
        if e in counts:
            counts[e] += 1
        else:
            counts[e] = 1
    m = None
    n = 0
    for (e, c) in counts.items():
        if c > n:
            n = c
            m = e
    return m


def geoip_and_best_guess_country_code(cell_keys, request, api_name):
    """
    Return (geoip, alpha2) where geoip is the result of a GeoIP lookup
    and alpha2 is a best-guess ISO 3166 alpha2 country code. The country
    code guess uses both GeoIP and cell MCCs, preferring GeoIP. Return
    None for either field if no data is available.
    """

    stats_client = get_stats_client()
    geoip = None

    if request.client_addr:
        geoip = request.registry.geoip_db.geoip_lookup(request.client_addr)

    cell_countries = []
    cell_mccs = set()
    for cell_key in cell_keys:
        for c in mobile_codes.mcc(str(cell_key.mcc)):
            cell_countries.append(c.alpha2)
            cell_mccs.add(cell_key.mcc)

    if len(cell_mccs) > 1:
        stats_client.incr('%s.anomaly.multiple_mccs' % api_name)

    if geoip:
        # GeoIP always wins if we have it.
        accuracy, city = radius_from_geoip(geoip)
        if city:
            stats_client.incr('%s.geoip_city_found' % api_name)
        else:
            stats_client.incr('%s.geoip_country_found' % api_name)

        if cell_countries and geoip['country_code'] not in cell_countries:
            stats_client.incr('%s.anomaly.geoip_mcc_mismatch' % api_name)

        stats_client.incr('%s.country_from_geoip' % api_name)
        geoip_res = {
            'lat': geoip['latitude'],
            'lon': geoip['longitude'],
            'accuracy': accuracy
        }
        return (geoip_res, geoip['country_code'])

    else:
        stats_client.incr('%s.no_geoip_found' % api_name)

    # Pick the most-commonly-occurring country code if we got any
    cc = most_common(cell_countries)
    if cc:
        stats_client.incr('%s.country_from_mcc' % api_name)
        return (None, cc)

    stats_client.incr('%s.no_country' % api_name)
    return (None, None)


def search_all_sources(request, data, api_name):
    """
    Common code-path for both the search and geolocate APIs, searching
    wifi, cell, cell-lac and GeoIP data sources.

    Arguments:
    request -- the original HTTP request object
    data -- a dict conforming to the search API
    api_name -- a string to use in Heka metrics ("search" or "geolocate")
    """

    stats_client = get_stats_client()
    heka_client = get_heka_client()

    session = request.db_slave_session
    result = None
    result_metric = None

    validated = {
        'wifi': [],
        'cell': [],
        'cell_lac': set(),
        'cell_network': [],
        'cell_lac_network': [],
    }

    # Pass-through wifi data
    validated['wifi'] = data.get('wifi', [])

    # Pre-process cell data
    radio = RADIO_TYPE.get(data.get('radio', ''), -1)
    for cell in data.get('cell', ()):
        cell = normalized_cell_dict(cell, default_radio=radio)
        if cell:
            cell_key = to_cellkey(cell)
            validated['cell'].append(cell_key)
            validated['cell_lac'].add(cell_key._replace(cid=CELLID_LAC))

    # Merge all possible cell and lac keys into one list
    all_cell_keys = []
    all_cell_keys.extend(validated['cell'])
    for key in validated['cell_lac']:
        all_cell_keys.append(key)

    # Do a single query for all cells and lacs at the same time
    try:
        all_networks = query_cell_networks(session, all_cell_keys)
    except Exception:
        heka_client.raven(RAVEN_ERROR)
        all_networks = []
    for network in all_networks:
        if network.key == CELLID_LAC:
            validated['cell_lac_network'].append(network)
        else:
            validated['cell_network'].append(network)

    # Always do a GeoIP lookup because we at _least_ want to use the
    # country estimate to filter out bogus requests. We may also use
    # the full GeoIP City-level estimate as well, if all else fails.
    (geoip_res, country) = geoip_and_best_guess_country_code(
        validated['cell'], request, api_name)

    # First we attempt a "zoom-in" from cell-lac, to cell
    # to wifi, tightening our estimate each step only so
    # long as it doesn't contradict the existing best-estimate
    # nor the country of origin.

    for (data_field, object_field, metric_name, search_fn) in [
            ('cell_lac', 'cell_lac_network', 'cell_lac', search_cell_lac),
            ('cell', 'cell_network', 'cell', search_cell),
            ('wifi', 'wifi', 'wifi', search_wifi)]:

        if validated[data_field]:
            try:
                r = search_fn(session, validated[object_field])
            except Exception:
                heka_client.raven(RAVEN_ERROR)
                stats_client.incr('%s.%s_error' %
                                  (api_name, metric_name))

            if r is None:
                stats_client.incr('%s.no_%s_found' %
                                  (api_name, metric_name))

            else:
                lat = float(r['lat'])
                lon = float(r['lon'])

                stats_client.incr('%s.%s_found' %
                                  (api_name, metric_name))

                # Skip any hit that seems to be in the wrong country.
                if country and not location_is_in_country(lat, lon,
                                                          country, 1):
                    stats_client.incr('%s.anomaly.%s_country_mismatch' %
                                      (api_name, metric_name))

                # Otherwise at least accept the first result we get.
                elif result is None:
                    result = r
                    result_metric = metric_name

                # Or any result that appears to be an improvement over the
                # existing best guess.
                elif (distance(float(result['lat']),
                               float(result['lon']), lat, lon) * 1000
                      <= result['accuracy']):
                    result = r
                    result_metric = metric_name

                else:
                    stats_client.incr('%s.anomaly.%s_%s_mismatch' %
                                      (api_name, metric_name, result_metric))

    # Fall back to GeoIP if nothing has worked yet. We do not
    # include this in the "zoom-in" loop because GeoIP is
    # frequently _wrong_ at the city level; we only want to
    # accept that estimate if we got nothing better from cell
    # or wifi.
    if not result and geoip_res:
        result = geoip_res
        result_metric = 'geoip'

    if not result:
        stats_client.incr('%s.miss' % api_name)
        return None

    stats_client.incr('%s.%s_hit' % (api_name, result_metric))
    stats_client.timing('%s.accuracy.%s' % (api_name, result_metric),
                        result['accuracy'])
    return result


@check_api_key('search', True)
def search_view(request):
    data, errors = preprocess_request(
        request,
        schema=SearchSchema(),
        extra_checks=(check_cell_or_wifi, ),
        accept_empty=True,
    )

    result = search_all_sources(request, data, "search")

    if not result:
        return {'status': 'not_found'}

    return {
        'status': 'ok',
        'lat': result['lat'],
        'lon': result['lon'],
        'accuracy': result['accuracy'],
    }


def map_data(data):
    """
    Transform a geolocate API dictionary to an equivalent search API
    dictionary.
    """
    if not data:
        return data

    mapped = {
        'radio': data['radioType'],
        'cell': [],
        'wifi': [],
    }

    if 'cellTowers' in data:
        for cell in data['cellTowers']:
            new_cell = {
                'mcc': cell['mobileCountryCode'],
                'mnc': cell['mobileNetworkCode'],
                'lac': cell['locationAreaCode'],
                'cid': cell['cellId'],
            }
            # If a radio field is populated in any one of the cells in
            # cellTowers, this is a buggy geolocate call from FirefoxOS.
            # Just pass on the radio field, as long as it's non-empty.
            if 'radio' in cell and cell['radio'] != '':
                new_cell['radio'] = cell['radio']
            mapped['cell'].append(new_cell)

    if 'wifiAccessPoints' in data:
        mapped['wifi'] = [{
            'key': wifi['macAddress'],
        } for wifi in data['wifiAccessPoints']]

    return mapped
