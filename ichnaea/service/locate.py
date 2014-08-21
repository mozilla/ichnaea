from collections import defaultdict, namedtuple
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
    OCIDCell,
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
from ichnaea.stats import get_stats_client

# parameters for wifi clustering
MAX_WIFI_CLUSTER_KM = 0.5
MIN_WIFIS_IN_QUERY = 2
MIN_WIFIS_IN_CLUSTER = 2
MAX_WIFIS_IN_CLUSTER = 5

# helper class used in searching
Network = namedtuple('Network', ['key', 'lat', 'lon', 'range'])


def estimate_accuracy(lat, lon, points, minimum):
    """
    Return the maximum range between a position (lat/lon) and a
    list of secondary positions (points). But at least use the
    specified minimum value.
    """
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
        accuracy = float(accuracy)
    return max(accuracy, minimum)


def most_common_elements(iterable):
    """
    Given an iterable, return a list of elements from that iterable:
        * If the iterable is empty, return an empty list.
        * If there is one element that's most common in the iterable,
          return a list with that element.
        * If there are multiple elements which occur equally often,
          return a list with all of those elements.
    """
    counts = defaultdict(int)
    for e in iterable:
        counts[e] += 1

    if not counts:
        return []

    max_count = max(counts.values())
    return [e for e, n in counts.items() if n == max_count]


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


def query_cell_table(model, session, cell_keys):

    cell_filter = []
    for key in cell_keys:
        # create a list of 'and' criteria for cell keys
        criterion = join_cellkey(model, key)
        cell_filter.append(and_(*criterion))

    # Keep the cid to distinguish cell from lac later on
    query = session.query(
        model.radio, model.mcc, model.mnc, model.lac, model.cid,
        model.lat, model.lon, model.range).filter(
        or_(*cell_filter)).filter(
        model.lat.isnot(None)).filter(
        model.lon.isnot(None))

    return query.all()


def query_cell_networks(session, cell_keys):
    if not cell_keys:
        return []

    result = query_cell_table(Cell, session, cell_keys)
    result.extend(query_cell_table(OCIDCell, session, cell_keys))

    if not result:
        return []

    # Group all results by location area
    lacs = defaultdict(list)
    for cell in result:
        lacs[cell[:4]].append(cell)

    def sort_lac(v):
        # use the lac with the most values, or the one with the smallest range
        return (len(v), -min([e[-1] for e in v]))

    # If we get data from multiple location areas, use the one with the
    # most data points in it. That way a lac with a cell hit will
    # have two entries and win over a lac with only the lac entry.
    lac = sorted(lacs.values(), key=sort_lac, reverse=True)

    cells = []
    for cell in lac[0]:
        # The first entry is the key, used only to distinguish cell from lac
        cells.append(Network(*cell[4:]))

    return cells


def geoip_and_best_guess_country_codes(cell_keys, api_name,
                                       client_addr, geoip_db):
    """
    Return (geoip, alpha2) where geoip is the result of a GeoIP lookup
    and alpha2 is a best-guess ISO 3166 alpha2 country code. The country
    code guess uses both GeoIP and cell MCCs, preferring GeoIP. Return
    None for either field if no data is available.
    """

    stats_client = get_stats_client()
    geoip = None

    if client_addr and geoip_db is not None:
        geoip = geoip_db.geoip_lookup(client_addr)

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

        if geoip['country_code'] not in cell_countries:
            if cell_countries:
                stats_client.incr('%s.anomaly.geoip_mcc_mismatch' % api_name)
            # Only use the GeoIP country as an additional possible match,
            # but retain the cell countries as a likely match as well.
            cell_countries.append(geoip['country_code'])

        stats_client.incr('%s.country_from_geoip' % api_name)
        geoip_res = {
            'lat': geoip['latitude'],
            'lon': geoip['longitude'],
            'accuracy': accuracy
        }
        return (geoip_res, most_common_elements(cell_countries))

    else:
        stats_client.incr('%s.no_geoip_found' % api_name)

    # Pick the most-commonly-occurring country codes if we got any
    cc = most_common_elements(cell_countries)
    if cc:
        stats_client.incr('%s.country_from_mcc' % api_name)
        return (None, cc)

    stats_client.incr('%s.no_country' % api_name)
    return (None, [])


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
    accuracy = float(accuracy)
    return {
        'lat': lac.lat,
        'lon': lac.lon,
        'accuracy': accuracy,
    }


def cluster_elements(elts, dist, thresh):
    """
    Generic pairwise clustering routine.

    :param elts: A list of elemenets to cluster.
    :param dist: A pairwise distance function over elements.
    :param thresh: A numeric threshold for clustering;
                   clusters P, Q will be joined if dist(a,b) <= thresh,
                   for any a in P, b in Q.

    :returns: A list of lists of elements, each sub-list being a cluster.
    """
    elts = list(elts)
    distance_matrix = [[dist(a, b) for a in elts] for b in elts]
    n = len(elts)
    clusters = [[i] for i in range(n)]

    def cluster_distance(a, b):
        return min([distance_matrix[i][j] for i in a for j in b])

    merged_one = True
    while merged_one:
        merged_one = False
        m = len(clusters)
        for i in range(m):
            if merged_one:
                break
            for j in range(m):
                if merged_one:
                    break
                if i == j:
                    continue
                a = clusters[i]
                b = clusters[j]
                if cluster_distance(a, b) <= thresh:
                    clusters.pop(j)
                    a.extend(b)
                    merged_one = True

    return [[elts[i] for i in c] for c in clusters]


def filter_bssids_by_similarity(bs):
    # Cluster BSSIDs by "similarity" (hamming or arithmetic distance);
    # return one BSSID from each cluster. The distance threshold is
    # hard-wired to 2, meaning that two BSSIDs are clustered together
    # if they are within a numeric difference of 2 of one another or
    # a hamming distance of 2.

    DISTANCE_THRESHOLD = 2

    def bytes_of_hex_string(hs):
        return [int(hs[i:i+2], 16) for i in range(0, len(hs), 2)]

    def hamming_distance(a, b):
        h = 0
        v = a ^ b
        while v:
            h += 1
            v &= v - 1
        return h

    def hamming_or_arithmetic_byte_difference(a, b):
        return min(abs(a - b), hamming_distance(a, b))

    def bssid_difference(a, b):
        abytes = bytes_of_hex_string(a)
        bbytes = bytes_of_hex_string(b)
        return sum(hamming_or_arithmetic_byte_difference(a, b) for
                   (a, b) in zip(abytes, bbytes))

    clusters = cluster_elements(bs, bssid_difference, DISTANCE_THRESHOLD)
    return [c[0] for c in clusters]


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

    # Filter out BSSIDs that are numerically very similar, assuming they're
    # multiple interfaces on the same base station or such.
    dissimilar_keys = set(filter_bssids_by_similarity([w[0] for w in wifis]))

    wifis = [Network(normalized_wifi_key(w[0]), w[1], w[2], w[3])
             for w in wifis
             if w[0] in dissimilar_keys]

    if len(wifis) < MIN_WIFIS_IN_QUERY:
        # We didn't get enough matches.
        return None

    # Sort networks by signal strengths in query.
    wifis.sort(lambda a, b: cmp(wifi_signals[b.key],
                                wifi_signals[a.key]))

    clusters = cluster_elements(wifis,
                                lambda a, b: distance(a.lat, a.lon,
                                                      b.lat, b.lon),
                                MAX_WIFI_CLUSTER_KM)

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

    clusters = [c for c in clusters if len(c) >= MIN_WIFIS_IN_CLUSTER]

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


def search_all_sources(session, api_name, data,
                       client_addr=None, geoip_db=None):
    """
    Common code-path for all lookup APIs, using
    WiFi, cell, cell-lac and GeoIP data sources.

    :param session: A database session for queries.
    :param api_name: A string to use in metrics (for example "geolocate").
    :param data: A dict conforming to the search API.
    :param client_addr: The IP address the request came from.
    :param geoip_db: The geoip database.
    """

    stats_client = get_stats_client()
    heka_client = get_heka_client()

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

    # Always do a GeoIP lookup because it is cheap and we want to
    # report geoip vs. other data mismatches. We may also use
    # the full GeoIP City-level estimate as well, if all else fails.
    (geoip_res, countries) = geoip_and_best_guess_country_codes(
        validated['cell'], api_name, client_addr, geoip_db)

    # First we attempt a "zoom-in" from cell-lac, to cell
    # to wifi, tightening our estimate each step only so
    # long as it doesn't contradict the existing best-estimate
    # nor the possible countries of origin.

    for (data_field, object_field, metric_name, search_fn) in [
            ('cell_lac', 'cell_lac_network', 'cell_lac', search_cell_lac),
            ('cell', 'cell_network', 'cell', search_cell),
            ('wifi', 'wifi', 'wifi', search_wifi)]:

        if validated[data_field]:
            r = None
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

                # Skip any hit that matches none of the possible countries.
                country_match = False
                for country in countries:
                    if location_is_in_country(lat, lon, country, 1):
                        country_match = True
                        break

                if countries and not country_match:
                    stats_client.incr('%s.anomaly.%s_country_mismatch' %
                                      (api_name, metric_name))

                # Always accept the first result we get.
                if result is None:
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

    rounded_result = {
        'lat': round(result['lat'], DEGREE_DECIMAL_PLACES),
        'lon': round(result['lon'], DEGREE_DECIMAL_PLACES),
        'accuracy': round(result['accuracy'], DEGREE_DECIMAL_PLACES),
    }

    stats_client.incr('%s.%s_hit' % (api_name, result_metric))
    stats_client.timing('%s.accuracy.%s' % (api_name, result_metric),
                        rounded_result['accuracy'])

    return rounded_result
