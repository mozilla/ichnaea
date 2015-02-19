from collections import defaultdict, namedtuple
import operator

import iso3166
from sqlalchemy.sql import and_, or_
from sqlalchemy.orm import load_only

from ichnaea.constants import (
    CELL_MIN_ACCURACY,
    DEGREE_DECIMAL_PLACES,
    LAC_MIN_ACCURACY,
    WIFI_MIN_ACCURACY,
)
from ichnaea.data.validation import (
    normalized_cell_dict,
    normalized_wifi_dict,
)
from ichnaea.geocalc import (
    distance,
)
from ichnaea.logging import (
    RAVEN_ERROR,
    get_heka_client,
    get_stats_client,
)
from ichnaea.models import (
    Cell,
    CellArea,
    OCIDCell,
    RADIO_TYPE,
    Wifi,
    join_cellkey,
    to_cellkey,
)

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


class StatsLogger(object):

    def __init__(self, api_key_name, api_key_log, api_name):
        """
        A StatsLogger sends counted and timed named statistics to
        a statistic aggregator client.

        :param api_key_name: Human readable API key name
            (for example 'test_1')
        :type api_key_name: str
        :param api_key_log: Gather additional API key specific stats?
        :type api_key_log: bool
        :param api_name: Name of the API, used as stats prefix
            (for example 'geolocate')
        :type api_name: str
        """
        self.api_key_name = api_key_name
        self.api_key_log = api_key_log
        self.api_name = api_name
        self.stats_client = get_stats_client()

    def stat_count(self, stat):
        self.stats_client.incr('{api}.{stat}'.format(
            api=self.api_name, stat=stat))

    def stat_time(self, stat, count):
        self.stats_client.timing('{api}.{stat}'.format(
            api=self.api_name, stat=stat), count)


class AbstractLocationProvider(StatsLogger):
    """
    An AbstractLocationProvider provides an interface for a class
    which will provide a location given a set of query data.

    .. attribute:: data_field

        The key to look for in the query data, for example 'cell'

    .. attribute:: log_name

        The name to use in logging statements, for example 'cell_lac'
    """

    data_field = None
    log_name = None

    def __init__(self, session, *args, **kwargs):
        self.session = session
        self.heka_client = get_heka_client()
        super(AbstractLocationProvider, self).__init__(*args, **kwargs)

    def locate(self, data):  # pragma: no cover
        """Provide a location given the provided query data (dict)."""
        raise NotImplementedError()

    def log_used(self):
        """Log a stat metric for a successful provider lookup."""
        if self.api_key_log:
            self.stat_count('api_log.{key}.{metric}_hit'.format(
                key=self.api_key_name, metric=self.log_name))

    def log_unused(self):
        """Log a stat metric for an unsuccessful provider lookup."""
        if self.api_key_log:
            self.stat_count('api_log.{key}.{metric}_miss'.format(
                key=self.api_key_name, metric=self.log_name))

    def has_data(self, data):
        """
        Does the query data (dict) contain information specific
        to this provider?

        :rtype: bool
        """
        return self.data_field in data


class AbstractCellLocationProvider(AbstractLocationProvider):
    """
    An AbstractCellLocationProvider provides an interface and
    partial implementation of a location search using a set of
    models which have a Cell-like set of fields.

    .. attribute:: models

        A list of models which have a Cell interface to be used
        in the location search.
    """
    models = []
    data_field = 'cell'

    def clean_cell_keys(self, data):
        """Pre-process cell data."""
        radio = RADIO_TYPE.get(data.get('radio', ''), -1)
        cell_keys = []
        for cell in data.get(self.data_field, ()):
            cell = normalized_cell_dict(cell, default_radio=radio)
            if cell:
                cell_key = to_cellkey(cell)
                cell_keys.append(cell_key)

        return cell_keys

    def query_database(self, cell_keys):
        """Query all cell models."""
        queried_objects = []
        for model in self.models:
            found_cells = []

            cell_filter = []
            for key in cell_keys:
                # create a list of 'and' criteria for cell keys
                criterion = join_cellkey(model, key)
                cell_filter.append(and_(*criterion))

            if cell_filter:
                # only do a query if we have cell results, or this will match
                # all rows in the table
                load_fields = (
                    'radio', 'mcc', 'mnc', 'lac', 'lat', 'lon', 'range')
                query = (self.session.query(model)
                                     .options(load_only(*load_fields))
                                     .filter(or_(*cell_filter))
                                     .filter(model.lat.isnot(None))
                                     .filter(model.lon.isnot(None)))

                try:
                    found_cells.extend(query.all())
                except Exception:
                    self.heka_client.raven(RAVEN_ERROR)

            if found_cells:
                # Group all found_cellss by location area
                lacs = defaultdict(list)
                for cell in found_cells:
                    cellarea_key = (cell.radio, cell.mcc, cell.mnc, cell.lac)
                    lacs[cellarea_key].append(cell)

                def sort_lac(v):
                    # use the lac with the most values,
                    # or the one with the smallest range
                    return (len(v), -min([e.range for e in v]))

                # If we get data from multiple location areas, use the one
                # with the most data points in it. That way a lac with a cell
                # hit will have two entries and win over a lac with only the
                # lac entry.
                lac = sorted(lacs.values(), key=sort_lac, reverse=True)

                for cell in lac[0]:
                    # The first entry is the key,
                    # used only to distinguish cell from lac
                    network = Network(
                        key=None,
                        lat=cell.lat,
                        lon=cell.lon,
                        range=cell.range)
                    queried_objects.append(network)

        return queried_objects

    def prepare_location(self, queried_objects):  # pragma: no cover
        """Combine the queried_objects into an estimated location."""
        raise NotImplementedError

    def locate(self, data):
        cell_keys = self.clean_cell_keys(data)
        queried_objects = self.query_database(cell_keys)
        if queried_objects:
            return self.prepare_location(queried_objects)


class CellLocationProvider(AbstractCellLocationProvider):
    """
    A CellLocationProvider implements a cell location search using
    the Cell and OCID Cell models.
    """
    models = [Cell, OCIDCell]
    log_name = 'cell'

    def prepare_location(self, queried_objects):
        self.stat_count('cell_hit')
        length = len(queried_objects)
        avg_lat = sum([c.lat for c in queried_objects]) / length
        avg_lon = sum([c.lon for c in queried_objects]) / length
        return {
            'lat': avg_lat,
            'lon': avg_lon,
            'accuracy': estimate_accuracy(
                avg_lat, avg_lon, queried_objects, CELL_MIN_ACCURACY),
        }


class CellAreaLocationProvider(AbstractCellLocationProvider):
    """
    A CellAreaLocationProvider implements a cell location search
    using the CellArea model.
    """
    models = [CellArea]
    log_name = 'cell_lac'

    def prepare_location(self, queried_objects):
        self.stat_count('cell_lac_hit')
        # take the smallest LAC of any the user is inside
        lac = sorted(queried_objects, key=operator.attrgetter('range'))[0]
        accuracy = max(LAC_MIN_ACCURACY, lac.range)
        accuracy = float(accuracy)
        return {
            'lat': lac.lat,
            'lon': lac.lon,
            'accuracy': accuracy,
        }


class WifiLocationProvider(AbstractLocationProvider):
    """
    A WifiLocationProvider implements a location search using
    the WiFi models and a series of clustering algorithms.
    """
    data_field = 'wifi'
    log_name = 'wifi'

    def cluster_elements(self, items, distance_fn, threshold):
        """
        Generic pairwise clustering routine.

        :param items: A list of elements to cluster.
        :param distance_fn: A pairwise distance_fnance function over elements.
        :param threshold: A numeric threshold for clustering;
                          clusters P, Q will be joined if
                          distance_fn(a,b) <= threshold,
                          for any a in P, b in Q.

        :returns: A list of lists of elements, each sub-list being a cluster.
        """
        distance_matrix = [[distance_fn(a, b) for a in items] for b in items]
        clusters = [[i] for i in range(len(items))]

        def cluster_distance(a, b):
            return min([distance_matrix[i][j] for i in a for j in b])

        merged_one = True
        while merged_one:
            merged_one = False
            for i in range(len(clusters)):
                if merged_one:
                    break
                for j in range(len(clusters)):
                    if merged_one:
                        break
                    if i == j:
                        continue
                    a = clusters[i]
                    b = clusters[j]
                    if cluster_distance(a, b) <= threshold:
                        clusters.pop(j)
                        a.extend(b)
                        merged_one = True

        return [[items[i] for i in c] for c in clusters]

    def filter_bssids_by_similarity(self, bs):
        """
        Cluster BSSIDs by "similarity" (hamming or arithmetic distance);
        return one BSSID from each cluster. The distance threshold is
        hard-wired to 2, meaning that two BSSIDs are clustered together
        if they are within a numeric difference of 2 of one another or
        a hamming distance of 2.
        """

        DISTANCE_THRESHOLD = 2

        def bytes_of_hex_string(hs):
            return [int(hs[i:i + 2], 16) for i in range(0, len(hs), 2)]

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

        clusters = self.cluster_elements(
            bs, bssid_difference, DISTANCE_THRESHOLD)
        return [c[0] for c in clusters]

    def get_clean_wifi_keys(self, data):
        wifis = []

        # Pre-process wifi data
        for wifi in data.get(self.data_field, ()):
            wifi = normalized_wifi_dict(wifi)
            if wifi:
                wifis.append(wifi)

        # Estimate signal strength at -100 dBm if none is provided,
        # which is worse than the 99th percentile of wifi dBms we
        # see in practice (-98).

        wifi_signals = dict([(w['key'], w['signal'] or -100) for w in wifis])
        wifi_keys = set(wifi_signals.keys())

        return (wifis, wifi_signals, wifi_keys)

    def query_database(self, wifi_keys):
        queried_wifis = []
        if len(wifi_keys) >= MIN_WIFIS_IN_QUERY:
            try:
                queried_wifis = (self.session.query(Wifi.key, Wifi.lat,
                                                    Wifi.lon, Wifi.range)
                                             .filter(Wifi.key.in_(wifi_keys))
                                             .filter(Wifi.lat.isnot(None))
                                             .filter(Wifi.lon.isnot(None))
                                             .all())
            except Exception:
                self.heka_client.raven(RAVEN_ERROR)
                self.stat_count('wifi_error')

        return queried_wifis

    def get_clusters(self, wifi_signals, queried_wifis):
        """
        Filter out BSSIDs that are numerically very similar, assuming they're
        multiple interfaces on the same base station or such.
        """
        dissimilar_keys = set(self.filter_bssids_by_similarity(
            [w.key for w in queried_wifis]))

        if len(dissimilar_keys) < len(queried_wifis):
            self.stat_time(
                'wifi.provided_too_similar',
                len(queried_wifis) - len(dissimilar_keys))

        wifi_networks = [
            Network(w.key, w.lat, w.lon, w.range)
            for w in queried_wifis if w.key in dissimilar_keys]

        if len(wifi_networks) < MIN_WIFIS_IN_QUERY:
            # We didn't get enough matches.
            self.stat_count('wifi.found_too_few')

        # Sort networks by signal strengths in query.
        wifi_networks.sort(
            lambda a, b: cmp(wifi_signals[b.key], wifi_signals[a.key]))

        clusters = self.cluster_elements(
            wifi_networks,
            lambda a, b: distance(a.lat, a.lon, b.lat, b.lon),
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

        return [c for c in clusters if len(c) >= MIN_WIFIS_IN_CLUSTER]

    def prepare_location(self, clusters):
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

    def has_data(self, data):
        if super(WifiLocationProvider, self).has_data(data):
            wifis, wifi_signals, wifi_keys = self.get_clean_wifi_keys(data)
            return (
                wifi_keys and
                len(
                    self.filter_bssids_by_similarity(list(wifi_keys))
                ) >= MIN_WIFIS_IN_QUERY
            )

    def locate(self, data):
        location = None

        wifis, wifi_signals, wifi_keys = self.get_clean_wifi_keys(data)

        if len(wifi_keys) < MIN_WIFIS_IN_QUERY:
            # We didn't get enough keys.
            if len(wifi_keys) >= 1:
                self.stat_count('wifi.provided_too_few')
        else:
            self.stat_time('wifi.provided', len(wifi_keys))

            queried_wifis = self.query_database(wifi_keys)

            if len(queried_wifis) < len(wifi_keys):
                self.stat_count('wifi.partial_match')
                self.stats_client.timing(
                    '{api}.wifi.provided_not_known'.format(api=self.api_name),
                    len(wifi_keys) - len(queried_wifis))

            clusters = self.get_clusters(wifi_signals, queried_wifis)

            if len(clusters) == 0:
                self.stat_count('wifi.found_no_cluster')
            else:
                self.stat_count('wifi_hit')
                location = self.prepare_location(clusters)

        return location


class GeoIPLocationProvider(AbstractLocationProvider):
    """
    A GeoIPLocationProvider implements a location search using a
    GeoIP client service lookup.
    """
    log_name = 'geoip'

    def __init__(self, geoip_db, *args, **kwargs):
        self.geoip_db = geoip_db
        super(GeoIPLocationProvider, self).__init__(*args, **kwargs)

    def has_data(self, data):
        return True

    def locate(self, client_addr):
        """
        Return (geoip, alpha2) where geoip is the result of a GeoIP lookup
        and alpha2 is a best-guess ISO 3166 alpha2 country code. Return
        None for either field if no data is available.
        """
        location = None
        country = None

        if client_addr and self.geoip_db is not None:
            geoip = self.geoip_db.geoip_lookup(client_addr)

            if geoip:
                if geoip['city']:
                    self.stat_count('geoip_city_found')
                else:
                    self.stat_count('geoip_country_found')
                self.stat_count('geoip_hit')

                # Only use the GeoIP country as an additional possible match,
                # but retain the cell countries as a likely match as well.
                country = geoip['country_code']
                location = {
                    'lat': geoip['latitude'],
                    'lon': geoip['longitude'],
                    'accuracy': geoip['accuracy'],
                }

        return (location, country)


class AbstractLocationSearcher(StatsLogger):
    """
    An AbstractLocationSearcher will use a collection of LocationProvider
    classes to attempt to identify a user's location. It will loop over them
    in the order they are specified and use the most accurate result.
    """
    # First we attempt a "zoom-in" from cell-lac, to cell
    # to wifi, tightening our estimate each step only so
    # long as it doesn't contradict the existing best-estimate.

    LOCATION_PROVIDER_CLASSES = (
        CellAreaLocationProvider,
        CellLocationProvider,
        WifiLocationProvider,
    )

    def __init__(self, session, geoip_db, *args, **kwargs):
        super(AbstractLocationSearcher, self).__init__(*args, **kwargs)
        self.session = session
        self.geoip_provider = GeoIPLocationProvider(
            api_key_log=self.api_key_log,
            api_key_name=self.api_key_name,
            api_name=self.api_name,
            geoip_db=geoip_db,
            session=self.session,
        )
        self.heka_client = get_heka_client()

        self.search_location_providers = [
            cls(
                api_key_log=self.api_key_log,
                api_key_name=self.api_key_name,
                api_name=self.api_name,
                session=self.session
            ) for cls in self.LOCATION_PROVIDER_CLASSES]

        self.all_location_providers = (
            [self.geoip_provider] + self.search_location_providers)

    def search_location(self, data, client_addr):
        location = None
        location_provider_used = None

        # Always do a GeoIP lookup because it is cheap and we want to
        # report geoip vs. other data mismatches. We may also use
        # the full GeoIP City-level estimate as well, if all else fails.
        geoip_location, country = self.geoip_provider.locate(client_addr)

        for location_provider in self.search_location_providers:
            provider_location = location_provider.locate(data)

            if provider_location:
                if location is None:
                    # If this is our first hit, then we use it.
                    location = provider_location
                    location_provider_used = location_provider
                else:
                    # If this location is more accurate than our previous one,
                    # we'll use it.
                    provider_distance = distance(
                        location['lat'],
                        location['lon'],
                        provider_location['lat'],
                        provider_location['lon']
                    ) * 1000
                    if provider_distance <= location['accuracy']:
                        location = provider_location
                        location_provider_used = location_provider

        # Fall back to GeoIP if nothing has worked yet. We do not
        # include this in the "zoom-in" loop because GeoIP is
        # frequently _wrong_ at the city level; we only want to
        # accept that estimate if we got nothing better from cell
        # or wifi.
        if not location and geoip_location:
            location = geoip_location
            location_provider_used = self.geoip_provider

        if not location:
            self.stat_count('miss')

        for location_provider in reversed(self.all_location_providers):
            if location_provider.has_data(data):
                if location_provider is location_provider_used:
                    location_provider.log_used()
                else:
                    location_provider.log_unused()
                break

        return country, location

    def prepare_location(self, country, location):  # pragma: no cover
        raise NotImplementedError()

    def search(self, data, client_addr):
        country, location = self.search_location(data, client_addr)
        if location or country:
            return self.prepare_location(country, location)


class PositionLocationSearcher(AbstractLocationSearcher):
    """
    A PositionLocationSearcher will return a location search query
    in the form of a position defined by a latitude, a longitude, and
    an accuracy in meters.
    """

    def prepare_location(self, country, location):
        return {
            'lat': round(location['lat'], DEGREE_DECIMAL_PLACES),
            'lon': round(location['lon'], DEGREE_DECIMAL_PLACES),
            'accuracy': round(location['accuracy'], DEGREE_DECIMAL_PLACES),
        }


class CountryLocationSearcher(AbstractLocationSearcher):
    """
    A CountryLocationSearcher will return a location search query
    in the form of the name and code of the queried country.
    """

    def prepare_location(self, country_code, location):
        country = iso3166.countries.get(country_code)
        return {
            'country_name': country.name,
            'country_code': country.alpha2,
        }


def search_all_sources(session, api_name, data,
                       client_addr=None, geoip_db=None,
                       api_key_log=False, api_key_name=None,
                       result_type='position'):

    searchers = {
        'position': PositionLocationSearcher,
        'country': CountryLocationSearcher,
    }
    return searchers[result_type](
        api_key_log=api_key_log,
        api_key_name=api_key_name,
        api_name=api_name,
        session=session,
        geoip_db=geoip_db
    ).search(data, client_addr=client_addr)
