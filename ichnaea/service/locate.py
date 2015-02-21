from collections import defaultdict, deque, namedtuple
from functools import partial
import operator

import mobile_codes
from sqlalchemy.sql import and_, or_
from sqlalchemy.orm import load_only

from ichnaea.constants import (
    CELL_MIN_ACCURACY,
    DEGREE_DECIMAL_PLACES,
    LAC_MIN_ACCURACY,
    WIFI_MIN_ACCURACY,
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
    CellKeyMixin,
    OCIDCell,
    RADIO_TYPE,
    Wifi,
    WifiKeyMixin,
    join_cellkey,
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


def map_data(data, client_addr=None):
    """
    Transform a geolocate API dictionary to an equivalent search API
    dictionary.
    """
    mapped = {
        'geoip': None,
        'radio': data.get('radioType', None),
        'cell': [],
        'wifi': [],
    }
    if client_addr:
        mapped['geoip'] = client_addr

    if not data:
        return mapped

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


class AbstractResult(object):
    """The result of a location provider query."""

    def __init__(self, provider, priority=-1,
                 lat=None, lon=None, accuracy=None,
                 country_code=None, country_name=None, query_data=True):
        self.provider = provider
        self.priority = priority
        self.lat = self._round(lat)
        self.lon = self._round(lon)
        self.accuracy = self._round(accuracy)
        self.country_code = country_code
        self.country_name = country_name
        self.query_data = query_data

    def _round(self, value):
        if value is not None:
            value = round(value, DEGREE_DECIMAL_PLACES)
        return value

    def found(self):  # pragma: no cover
        """Does this result include any location data?"""
        raise NotImplementedError

    def agrees_with(self, result):  # pragma: no cover
        """Does this result match the position of the other result?"""
        raise NotImplementedError

    def accurate_enough(self):  # pragma: no cover
        """Is this result accurate enough to return it?"""
        raise NotImplementedError

    def more_accurate(self, result):  # pragma: no cover
        """Is this result better than the passed in result?"""
        raise NotImplementedError


class PositionResult(AbstractResult):
    """The result of a position query."""

    def found(self):
        return self.lat is not None and self.lon is not None

    def agrees_with(self, result):
        dist = distance(result.lat, result.lon, self.lat, self.lon) * 1000
        return dist <= result.accuracy

    def accurate_enough(self):
        # For position data we currently always want to continue.
        return False

    def more_accurate(self, result):
        """
        Are we more accurate than the passed in result and fit into
        the claimed result range?
        """
        if not self.found():
            return False
        if not result.found():
            return True
        if self.priority > result.priority:
            return True
        return self.agrees_with(result) and self.accuracy < result.accuracy


class CountryResult(AbstractResult):
    """The result of a country query."""

    def found(self):
        return self.country_code is not None and self.country_name is not None

    def agrees_with(self, result):  # pragma: no cover
        return self.country_code == result.country_code

    def accurate_enough(self):
        if self.found():
            return True
        return False

    def more_accurate(self, result):
        if not self.found():
            return False
        if not result.found():
            return True
        if self.priority > result.priority:  # pragma: no cover
            return True
        return False  # pragma: no cover


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
        self.heka_client = get_heka_client()
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

    .. attribute:: log_group

        The name of the logging group, for example 'cell' for both
        cell and cell location area providers.
    """

    db_source_field = 'session'
    data_field = None
    log_name = None
    log_group = None
    priority = 1
    result_type = None

    def __init__(self, db_source, result_type, *args, **kwargs):
        self.db_source = db_source
        self.result_type = partial(result_type, self, priority=self.priority)
        super(AbstractLocationProvider, self).__init__(*args, **kwargs)

    def locate(self, data):  # pragma: no cover
        """Provide a location given the provided query data (dict).

        :rtype: :class:`~ichnaea.service.locate.AbstractResult`
        """
        raise NotImplementedError()

    def log_hit(self):
        """Log a stat metric for a successful provider lookup."""
        self.stat_count('{metric}_hit'.format(metric=self.log_name))

    def log_success(self):
        """
        Log a stat metric for a request in which the user provided
        relevant data for this provider and the lookup was successful.
        """
        if self.api_key_log:
            self.stat_count('api_log.{key}.{metric}_hit'.format(
                key=self.api_key_name, metric=self.log_name))

    def log_failure(self):
        """
        Log a stat metric for a request in which the user provided
        relevant data for this provider and the lookup failed.
        """
        if self.api_key_log:
            self.stat_count('api_log.{key}.{metric}_miss'.format(
                key=self.api_key_name, metric=self.log_name))


class AbstractCellLocationProvider(AbstractLocationProvider):
    """
    An AbstractCellLocationProvider provides an interface and
    partial implementation of a location search using a set of
    models which have a Cell-like set of fields.

    .. attribute:: models

        A list of models which have a Cell interface to be used
        in the location search.
    """
    models = ()
    data_field = 'cell'
    log_name = 'cell'
    log_group = 'cell'

    def clean_cell_keys(self, data):
        """Pre-process cell data."""
        radio = RADIO_TYPE.get(data.get('radio', ''), -1)
        cell_keys = []
        for cell in data.get(self.data_field, ()):
            cell = CellKeyMixin.validate(cell, default_radio=radio)
            if cell:
                cell_key = CellKeyMixin.to_hashkey(cell)
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
                query = (self.db_source.query(model)
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
        """
        Combine the queried_objects into an estimated location.

        :rtype: :class:`~ichnaea.service.locate.AbstractResult`
        """
        raise NotImplementedError

    def locate(self, data):
        location = self.result_type(query_data=False)
        cell_keys = self.clean_cell_keys(data)
        if cell_keys:
            location.query_data = True
        queried_objects = self.query_database(cell_keys)
        if queried_objects:
            location = self.prepare_location(queried_objects)
        return location


class CellLocationProvider(AbstractCellLocationProvider):
    """
    A CellLocationProvider implements a cell location search using
    the Cell and OCID Cell models.
    """
    models = (Cell, OCIDCell)

    def prepare_location(self, queried_objects):
        length = len(queried_objects)
        avg_lat = sum([c.lat for c in queried_objects]) / length
        avg_lon = sum([c.lon for c in queried_objects]) / length
        accuracy = estimate_accuracy(
            avg_lat, avg_lon, queried_objects, CELL_MIN_ACCURACY)
        return self.result_type(lat=avg_lat, lon=avg_lon, accuracy=accuracy)


class CellAreaLocationProvider(AbstractCellLocationProvider):
    """
    A CellAreaLocationProvider implements a cell location search
    using the CellArea model.
    """
    models = (CellArea, )
    log_name = 'cell_lac'

    def prepare_location(self, queried_objects):
        # take the smallest LAC of any the user is inside
        lac = sorted(queried_objects, key=operator.attrgetter('range'))[0]
        accuracy = float(max(LAC_MIN_ACCURACY, lac.range))
        return self.result_type(lat=lac.lat, lon=lac.lon, accuracy=accuracy)


class CellCountryProvider(AbstractCellLocationProvider):
    """
    A CellCountryProvider implements a cell country search without
    using any DB models.
    """

    def query_database(self, cell_keys):
        countries = []
        for key in cell_keys:
            countries.extend(mobile_codes.mcc(str(key.mcc)))
        if len(set([c.alpha2 for c in countries])) != 1:
            # refuse to guess country if there are multiple choices
            return []
        return countries[0]

    def prepare_location(self, obj):
        return self.result_type(country_code=obj.alpha2,
                                country_name=obj.name)


class WifiLocationProvider(AbstractLocationProvider):
    """
    A WifiLocationProvider implements a location search using
    the WiFi models and a series of clustering algorithms.
    """
    data_field = 'wifi'
    log_name = 'wifi'
    log_group = 'wifi'

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
            wifi = WifiKeyMixin.validate(wifi)
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
                queried_wifis = (self.db_source.query(Wifi.key, Wifi.lat,
                                                      Wifi.lon, Wifi.range)
                                               .filter(Wifi.key.in_(wifi_keys))
                                               .filter(Wifi.lat.isnot(None))
                                               .filter(Wifi.lon.isnot(None))
                                               .all())
            except Exception:
                self.heka_client.raven(RAVEN_ERROR)

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
        accuracy = estimate_accuracy(avg_lat, avg_lon,
                                     sample, WIFI_MIN_ACCURACY)
        return self.result_type(lat=avg_lat, lon=avg_lon, accuracy=accuracy)

    def sufficient_data(self, wifi_keys):
        return (len(self.filter_bssids_by_similarity(list(wifi_keys))) >=
                MIN_WIFIS_IN_QUERY)

    def locate(self, data):
        location = self.result_type(query_data=False)

        wifis, wifi_signals, wifi_keys = self.get_clean_wifi_keys(data)

        if len(wifi_keys) < MIN_WIFIS_IN_QUERY:
            # We didn't get enough keys.
            if len(wifi_keys) >= 1:
                self.stat_count('wifi.provided_too_few')
        else:
            self.stat_time('wifi.provided', len(wifi_keys))

            if self.sufficient_data(wifi_keys):
                location.query_data = True

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
                location = self.prepare_location(clusters)

        return location


class GeoIPLocationProvider(AbstractLocationProvider):
    """
    A GeoIPLocationProvider implements a location search using a
    GeoIP client service lookup.
    """
    db_source_field = 'geoip'
    data_field = 'geoip'
    log_name = 'geoip'
    log_group = 'geoip'
    priority = 0

    def locate(self, data):
        """Provide a location given the provided client IP address.

        :rtype: :class:`~ichnaea.service.locate.AbstractResult`
        """
        # Always consider there to be GeoIP data, even if no client_addr
        # was provided
        location = self.result_type(query_data=True)
        client_addr = data.get(self.data_field, None)

        if client_addr and self.db_source is not None:
            geoip = self.db_source.geoip_lookup(client_addr)
            if geoip:
                if geoip['city']:
                    self.stat_count('geoip_city_found')
                else:
                    self.stat_count('geoip_country_found')

                location = self.result_type(
                    lat=geoip['latitude'],
                    lon=geoip['longitude'],
                    accuracy=geoip['accuracy'],
                    country_code=geoip['country_code'],
                    country_name=geoip['country_name'],
                )

        return location


class AbstractLocationSearcher(StatsLogger):
    """
    An AbstractLocationSearcher will use a collection of LocationProvider
    classes to attempt to identify a user's location. It will loop over them
    in the order they are specified and use the most accurate result.
    """
    # First we attempt a "zoom-in" from cell-lac, to cell
    # to wifi, tightening our estimate each step only so
    # long as it doesn't contradict the existing best-estimate.

    provider_classes = ()
    result_type = None

    def __init__(self, db_sources, *args, **kwargs):
        super(AbstractLocationSearcher, self).__init__(*args, **kwargs)

        self.all_providers = [
            cls(
                db_sources[cls.db_source_field],
                self.result_type,
                api_key_log=self.api_key_log,
                api_key_name=self.api_key_name,
                api_name=self.api_name,
            ) for cls in self.provider_classes]

    def search_location(self, data):
        result = self.result_type(None, query_data=False)
        all_results = defaultdict(deque)

        for location_provider in self.all_providers:
            provider_result = location_provider.locate(data)
            all_results[location_provider.log_group].appendleft(
                provider_result)

            if provider_result.more_accurate(result):
                # If this location is more accurate than our previous one,
                # we'll use it.
                result = provider_result

            if result.accurate_enough():
                # Stop the loop, if we have a good quality result.
                break

        if not result.found():
            self.stat_count('miss')
        else:
            result.provider.log_hit()

        # Log a hit/miss metric for the first data source for
        # which the user provided sufficient data
        for log_group in ('wifi', 'cell', 'geoip'):
            results = all_results[log_group]
            if any([r.query_data for r in results]):
                # Claim a success if at least one result for a logging
                # group was a success.
                first_result = results[0]
                found_result = None
                for res in results:
                    if res.found():
                        found_result = res
                        break
                if found_result is not None:
                    found_result.provider.log_success()
                else:
                    first_result.provider.log_failure()
                break

        return result

    def prepare_location(self, country, location):  # pragma: no cover
        raise NotImplementedError()

    def search(self, data):
        """Provide a type specific search result or return None."""
        result = self.search_location(data)
        if result.found():
            return self.prepare_location(result)
        return None


class PositionSearcher(AbstractLocationSearcher):
    """
    A PositionSearcher will return a position defined by a latitude,
    a longitude and an accuracy in meters.
    """

    provider_classes = (
        GeoIPLocationProvider,
        CellAreaLocationProvider,
        CellLocationProvider,
        WifiLocationProvider,
    )
    result_type = PositionResult

    def prepare_location(self, location):
        return {
            'lat': location.lat,
            'lon': location.lon,
            'accuracy': location.accuracy,
        }


class CountrySearcher(AbstractLocationSearcher):
    """
    A CountrySearcher will return a country name and code.
    """

    provider_classes = (
        CellCountryProvider,
        GeoIPLocationProvider,
    )
    result_type = CountryResult

    def prepare_location(self, location):
        return {
            'country_name': location.country_name,
            'country_code': location.country_code,
        }
