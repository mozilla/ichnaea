import operator
import simplejson as json
import time
from collections import defaultdict, namedtuple
from enum import IntEnum
from functools import partial

import mobile_codes
import requests
from redis import ConnectionError
from sqlalchemy.orm import load_only

from ichnaea.constants import (
    CELL_MIN_ACCURACY,
    LAC_MIN_ACCURACY,
    WIFI_MIN_ACCURACY,
)
from ichnaea.geocalc import distance
from ichnaea.models import (
    Cell,
    CellArea,
    OCIDCell,
    OCIDCellArea,
    Wifi,
)
from ichnaea.api.locate.location import Position, Country
from ichnaea.api.locate.schema import (
    CellAreaLookup,
    CellLookup,
    WifiLookup,
)
from ichnaea.api.locate.stats import StatsLogger
from ichnaea.rate_limit import rate_limit


# parameters for wifi clustering
MAX_WIFI_CLUSTER_KM = 0.5
MIN_WIFIS_IN_QUERY = 2
MIN_WIFIS_IN_CLUSTER = 2
MAX_WIFIS_IN_CLUSTER = 5

# helper class used in searching
Network = namedtuple('Network', ['key', 'lat', 'lon', 'range'])


# Data sources for location information. A smaller integer value
# represents a better overall quality of the data source.
class DataSource(IntEnum):
    Internal = 1
    OCID = 2
    Fallback = 3
    GeoIP = 4


class Provider(StatsLogger):
    """
    A Provider provides an interface for a class
    which will provide a location given a set of query data.

    .. attribute:: log_name

        The name to use in logging statements, for example 'cell_lac'
    """

    fallback_field = None
    log_name = None
    location_type = None
    source = DataSource.Internal

    def __init__(self, session_db, geoip_db,
                 redis_client, settings, *args, **kwargs):
        self.session_db = session_db
        self.geoip_db = geoip_db
        self.settings = settings
        self.redis_client = redis_client
        self.location_type = partial(
            self.location_type,
            source=self.source,
            fallback=self.fallback_field,
        )
        super(Provider, self).__init__(*args, **kwargs)

    def should_locate(self, data, location):
        """
        Given location query data and a possible location
        found by another provider, check if this provider should
        attempt to perform a location search.
        """
        if self.fallback_field is not None:
            try:
                fallbacks = data.get('fallbacks', {})
                if fallbacks:
                    return fallbacks.get(self.fallback_field, True)
            except ValueError:  # pragma: no cover
                self.raven_client.captureException()

        return True

    def locate(self, data):  # pragma: no cover
        """
        Provide a location given the provided query data (dict).

        :rtype: :class:`~ichnaea.api.locate.location.Location`
        """
        raise NotImplementedError()

    def _estimate_accuracy(self, lat, lon, points, minimum):
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

    def log_hit(self):
        """Log a stat metric for a successful provider lookup."""
        self.stat_count('{metric}_hit'.format(metric=self.log_name))

    def log_success(self):
        """
        Log a stat metric for a request in which the user provided
        relevant data for this provider and the lookup was successful.
        """
        if self.api_key.log:
            self.stat_count('api_log.{key}.{metric}_hit'.format(
                key=self.api_key.name, metric=self.log_name))

    def log_failure(self):
        """
        Log a stat metric for a request in which the user provided
        relevant data for this provider and the lookup failed.
        """
        if self.api_key.log:
            self.stat_count('api_log.{key}.{metric}_miss'.format(
                key=self.api_key.name, metric=self.log_name))


class BaseCellProvider(Provider):
    """
    An BaseCellProvider provides an interface and
    partial implementation of a search using a
    model which has a Cell-like set of fields.

    .. attribute:: model

        A model which has a Cell interface to be used
        in the location search.
    """
    model = None
    log_name = 'cell'
    location_type = Position
    validator = CellLookup

    def _clean_cell_keys(self, data):
        """Pre-process cell data."""
        cell_keys = []
        for cell in data.get('cell', ()):
            cell = self.validator.validate(cell)
            if cell:
                cell_key = self.validator.to_hashkey(cell)
                cell_keys.append(cell_key)

        return cell_keys

    def _query_database(self, cell_keys):
        """Query the cell model."""
        try:
            load_fields = ('lat', 'lon', 'range')
            cell_iter = self.model.iterkeys(
                self.session_db,
                cell_keys,
                extra=lambda query: query.options(load_only(*load_fields))
                                         .filter(self.model.lat.isnot(None))
                                         .filter(self.model.lon.isnot(None)))

            return self._filter_cells(list(cell_iter))
        except Exception:
            self.raven_client.captureException()
            return []

    def _filter_cells(self, found_cells):
        # Group all found_cells by location area
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
        if not lac:
            return []

        return [Network(
            key=None,
            lat=cell.lat,
            lon=cell.lon,
            range=cell.range,
        ) for cell in lac[0]]

    def _prepare(self, queried_cells):
        """
        Combine the queried_cells into an estimated location.

        :rtype: :class:`~ichnaea.api.locate.location.Location`
        """
        length = len(queried_cells)
        avg_lat = sum([c.lat for c in queried_cells]) / length
        avg_lon = sum([c.lon for c in queried_cells]) / length
        accuracy = self._estimate_accuracy(
            avg_lat, avg_lon, queried_cells, CELL_MIN_ACCURACY)
        return self.location_type(lat=avg_lat, lon=avg_lon, accuracy=accuracy)

    def locate(self, data):
        location = self.location_type(query_data=False)
        cell_keys = self._clean_cell_keys(data)
        if cell_keys:
            location.query_data = True
            queried_cells = self._query_database(cell_keys)
            if queried_cells:
                location = self._prepare(queried_cells)
        return location


class CellPositionProvider(BaseCellProvider):
    """
    A CellPositionProvider implements a cell search using the Cell model.
    """
    model = Cell


class OCIDCellPositionProvider(BaseCellProvider):
    """
    A OCIDCellPositionProvider implements a cell search using
    the OCID Cell model.
    """
    model = OCIDCell
    source = DataSource.OCID


class CellAreaPositionProvider(BaseCellProvider):
    """
    A CellAreaPositionProvider implements a cell search
    using the CellArea model.
    """
    model = CellArea
    log_name = 'cell_lac'
    validator = CellAreaLookup
    fallback_field = 'lacf'

    def _prepare(self, queried_cells):
        # take the smallest LAC of any the user is inside
        lac = sorted(queried_cells, key=operator.attrgetter('range'))[0]
        accuracy = float(max(LAC_MIN_ACCURACY, lac.range))
        return self.location_type(lat=lac.lat, lon=lac.lon, accuracy=accuracy)


class OCIDCellAreaPositionProvider(CellAreaPositionProvider):
    """
    A OCIDCellAreaPositionProvider implements a cell search
    using the OCIDCellArea model.
    """
    model = OCIDCellArea
    source = DataSource.OCID


class CellCountryProvider(BaseCellProvider):
    """
    A CellCountryProvider implements a cell country search without
    using any DB models.
    """
    location_type = Country

    def _query_database(self, cell_keys):
        countries = []
        for key in cell_keys:
            countries.extend(mobile_codes.mcc(str(key.mcc)))
        if len(set([c.alpha2 for c in countries])) != 1:
            # refuse to guess country if there are multiple choices
            return []
        return countries[0]

    def _prepare(self, obj):
        return self.location_type(country_code=obj.alpha2,
                                  country_name=obj.name)


class WifiPositionProvider(Provider):
    """
    A WifiPositionProvider implements a position search using
    the WiFi models and a series of clustering algorithms.
    """
    log_name = 'wifi'
    location_type = Position

    def _cluster_elements(self, items, distance_fn, threshold):
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

    def _filter_bssids_by_similarity(self, bs):
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

        clusters = self._cluster_elements(
            bs, bssid_difference, DISTANCE_THRESHOLD)
        return [c[0] for c in clusters]

    def _get_clean_wifi_keys(self, data):
        wifis = []

        # Pre-process wifi data
        for wifi in data.get('wifi', ()):
            wifi = WifiLookup.validate(wifi)
            if wifi:
                wifis.append(wifi)

        # Estimate signal strength at -100 dBm if none is provided,
        # which is worse than the 99th percentile of wifi dBms we
        # see in practice (-98).

        wifi_signals = dict([(w['key'], w['signal'] or -100) for w in wifis])
        wifi_keys = set(wifi_signals.keys())

        return (wifis, wifi_signals, wifi_keys)

    def _query_database(self, wifi_keys):
        try:
            load_fields = ('key', 'lat', 'lon', 'range')
            wifi_iter = Wifi.iterkeys(
                self.session_db,
                [Wifi.to_hashkey(key=key) for key in wifi_keys],
                extra=lambda query: query.options(load_only(*load_fields))
                                         .filter(Wifi.lat.isnot(None))
                                         .filter(Wifi.lon.isnot(None)))

            return list(wifi_iter)
        except Exception:
            self.raven_client.captureException()
            return []

    def _get_clusters(self, wifi_signals, queried_wifis):
        """
        Filter out BSSIDs that are numerically very similar, assuming they're
        multiple interfaces on the same base station or such.
        """
        dissimilar_keys = set(self._filter_bssids_by_similarity(
            [w.key for w in queried_wifis]))

        wifi_networks = [
            Network(w.key, w.lat, w.lon, w.range)
            for w in queried_wifis if w.key in dissimilar_keys]

        # Sort networks by signal strengths in query.
        wifi_networks.sort(key=lambda a: wifi_signals[a.key], reverse=True)

        clusters = self._cluster_elements(
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

    def _prepare(self, clusters):
        clusters.sort(key=lambda a: len(a), reverse=True)
        cluster = clusters[0]
        sample = cluster[:min(len(cluster), MAX_WIFIS_IN_CLUSTER)]
        length = len(sample)
        avg_lat = sum([n.lat for n in sample]) / length
        avg_lon = sum([n.lon for n in sample]) / length
        accuracy = self._estimate_accuracy(avg_lat, avg_lon,
                                           sample, WIFI_MIN_ACCURACY)
        return self.location_type(lat=avg_lat, lon=avg_lon, accuracy=accuracy)

    def _sufficient_data(self, wifi_keys):
        return (len(self._filter_bssids_by_similarity(list(wifi_keys))) >=
                MIN_WIFIS_IN_QUERY)

    def locate(self, data):
        location = self.location_type(query_data=False)

        wifis, wifi_signals, wifi_keys = self._get_clean_wifi_keys(data)

        if len(wifi_keys) >= MIN_WIFIS_IN_QUERY:
            if self._sufficient_data(wifi_keys):
                location.query_data = True

            queried_wifis = self._query_database(wifi_keys)
            clusters = self._get_clusters(wifi_signals, queried_wifis)

            if clusters:
                location = self._prepare(clusters)

        return location


class BaseGeoIPProvider(Provider):
    """
    A BaseGeoIPProvider implements a search using
    a GeoIP client service lookup.
    """
    fallback_field = 'ipf'
    log_name = 'geoip'
    source = DataSource.GeoIP

    def locate(self, data):
        """Provide a location given the provided client IP address.

        :rtype: :class:`~ichnaea.api.locate.location.Location`
        """
        # Always consider there to be GeoIP data, even if no client_addr
        # was provided
        location = self.location_type(query_data=True)
        client_addr = data.get('geoip', None)

        if client_addr and self.geoip_db is not None:
            geoip = self.geoip_db.geoip_lookup(client_addr)
            if geoip:
                if geoip['city']:
                    self.stat_count('geoip_city_found')
                else:
                    self.stat_count('geoip_country_found')

                location = self.location_type(
                    lat=geoip['latitude'],
                    lon=geoip['longitude'],
                    accuracy=geoip['accuracy'],
                    country_code=geoip['country_code'],
                    country_name=geoip['country_name'],
                )

        return location


class GeoIPPositionProvider(BaseGeoIPProvider):
    location_type = Position


class GeoIPCountryProvider(BaseGeoIPProvider):
    location_type = Country


class FallbackProvider(Provider):
    log_name = 'fallback'
    location_type = Position
    source = DataSource.Fallback
    LOCATION_NOT_FOUND = True

    def __init__(self, settings, *args, **kwargs):
        self.url = settings['url']
        self.ratelimit = int(settings.get('ratelimit', 0))
        self.rate_limit_expire = int(settings.get('ratelimit_expire', 0))
        self.cache_expire = int(settings.get('cache_expire', 0))
        super(FallbackProvider, self).__init__(
            settings=settings, *args, **kwargs)

    def _prepare_cell(self, cell):
        validated_cell = CellLookup.validate(cell)
        if validated_cell is None:
            return None

        radio = validated_cell.get('radio', None)
        if radio is not None:
            radio = radio.name
            if radio == 'umts':
                radio = 'wcdma'

        result = {}
        cell_map = {
            'mcc': 'mobileCountryCode',
            'mnc': 'mobileNetworkCode',
            'lac': 'locationAreaCode',
            'cid': 'cellId',
            'signal': 'signalStrength',
            'ta': 'timingAdvance',
        }
        if radio:
            result['radioType'] = radio
        for source, target in cell_map.items():
            if validated_cell.get(source):
                result[target] = validated_cell[source]

        return result

    def _prepare_wifi(self, wifi):
        validated_wifi = WifiLookup.validate(wifi)
        if validated_wifi is None:
            return None

        result = {}
        wifi_map = {
            'key': 'macAddress',
            'channel': 'channel',
            'signal': 'signalStrength',
            'snr': 'signalToNoiseRatio',
        }
        for source, target in wifi_map.items():
            if validated_wifi.get(source):
                result[target] = validated_wifi[source]

        return result

    def _prepare_data(self, data):
        cell_queries = []
        for cell in data.get('cell', []):
            cell_query = self._prepare_cell(cell)
            if cell_query:
                cell_queries.append(cell_query)

        wifi_queries = []
        for wifi in data.get('wifi', []):
            wifi_query = self._prepare_wifi(wifi)
            if wifi_query:
                wifi_queries.append(wifi_query)

        query = {}
        if cell_queries:
            query['cellTowers'] = cell_queries
        if wifi_queries:
            query['wifiAccessPoints'] = wifi_queries
        if 'fallbacks' in data and data['fallbacks']:
            query['fallbacks'] = {
                # We only send the lacf fallback for now
                'lacf': data['fallbacks'].get('lacf', 0),
            }

        return query

    def should_locate(self, data, location):
        empty_location = not location.found()
        weak_location = (location.source is not None and
                         location.source >= DataSource.GeoIP)

        query_data = self._prepare_data(data)
        cell_found = query_data.get('cellTowers', [])
        wifi_found = len(query_data.get('wifiAccessPoints', [])) > 1
        return (
            self.api_key.allow_fallback and
            (empty_location or weak_location) and
            (cell_found or wifi_found)
        )

    def get_ratelimit_key(self):
        return 'fallback_ratelimit:{time}'.format(time=int(time.time()))

    def limit_reached(self):
        return self.ratelimit and rate_limit(
            self.redis_client,
            self.get_ratelimit_key(),
            maxreq=self.ratelimit,
            expire=self.rate_limit_expire,
            fail_on_error=True,
        )

    def _should_cache(self, data):
        return (
            self.cache_expire and
            len(data.get('cell', [])) == 1 and
            len(data.get('wifi', [])) == 0
        )

    def _get_cache_key(self, cell_data):
        return 'fallback_cache_cell:{radio}:{mcc}:{mnc}:{lac}:{cid}'.format(
            radio=cell_data['radio'].name,
            mcc=cell_data['mcc'],
            mnc=cell_data['mnc'],
            lac=cell_data['lac'],
            cid=cell_data['cid'],
        )

    def _get_cached_result(self, data):
        if self._should_cache(data):
            all_cell_data = data.get('cell', [])
            cache_key = self._get_cache_key(all_cell_data[0])
            try:
                cached_cell = self.redis_client.get(cache_key)
                if cached_cell:
                    self.stat_count('fallback.cache.hit')
                    return json.loads(cached_cell)
                else:
                    self.stat_count('fallback.cache.miss')
            except ConnectionError:
                self.raven_client.captureException()

    def _set_cached_result(self, data, result):
        if self._should_cache(data):
            all_cell_data = data.get('cell', [])
            cache_key = self._get_cache_key(all_cell_data[0])
            try:
                self.redis_client.set(
                    cache_key,
                    json.dumps(result),
                    ex=self.cache_expire,
                )
            except ConnectionError:
                self.raven_client.captureException()

    def _make_external_call(self, data):
        query_data = self._prepare_data(data)

        try:
            with self.stat_timer('fallback.lookup'):
                response = requests.post(
                    self.url,
                    headers={'User-Agent': 'ichnaea'},
                    json=query_data,
                    timeout=5.0,
                    verify=False,
                )
            self.stat_count('fallback.lookup_status.%s' % response.status_code)
            if response.status_code != 404:
                # don't log exceptions for normal not found responses
                response.raise_for_status()
            else:
                return self.LOCATION_NOT_FOUND

            return response.json()

        except (json.JSONDecodeError, requests.exceptions.RequestException):
            self.raven_client.captureException()

    def locate(self, data):
        location = self.location_type(query_data=False)

        if not self.limit_reached():

            cached_location = self._get_cached_result(data)
            location_data = (
                cached_location or
                self._make_external_call(data)
            )

            if location_data and location_data is not self.LOCATION_NOT_FOUND:
                try:
                    location = self.location_type(
                        lat=location_data['location']['lat'],
                        lon=location_data['location']['lng'],
                        accuracy=location_data['accuracy'],
                    )
                except (KeyError, TypeError):
                    self.raven_client.captureException()

            if cached_location is None:
                self._set_cached_result(data, location_data)

        return location
