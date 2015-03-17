from collections import defaultdict, namedtuple
from enum import IntEnum
from functools import partial
import operator

import mobile_codes
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
    CellLookup,
    OCIDCell,
    OCIDCellArea,
    Wifi,
    WifiLookup,
)
from ichnaea.locate.location import PositionLocation, CountryLocation
from ichnaea.stats import StatsLogger


# parameters for wifi clustering
MAX_WIFI_CLUSTER_KM = 0.5
MIN_WIFIS_IN_QUERY = 2
MIN_WIFIS_IN_CLUSTER = 2
MAX_WIFIS_IN_CLUSTER = 5

# helper class used in searching
Network = namedtuple('Network', ['key', 'lat', 'lon', 'range'])


# Data sources for location information
class DataSource(IntEnum):
    Internal = 1
    OCID = 2
    GeoIP = 3


class LocationProvider(StatsLogger):
    """
    An LocationProvider provides an interface for a class
    which will provide a location given a set of query data.

    .. attribute:: data_field

        The key to look for in the query data, for example 'cell'

    .. attribute:: log_name

        The name to use in logging statements, for example 'cell_lac'
    """

    db_source_field = 'session'
    data_field = None
    log_name = None
    location_type = None
    source = DataSource.Internal

    def __init__(self, db_source, *args, **kwargs):
        self.db_source = db_source
        self.location_type = partial(self.location_type, source=self.source)
        super(LocationProvider, self).__init__(*args, **kwargs)

    def locate(self, data):  # pragma: no cover
        """Provide a location given the provided query data (dict).

        :rtype: :class:`~ichnaea.locate.Location`
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


class CellLocationProvider(LocationProvider):
    """
    An CellLocationProvider provides an interface and
    partial implementation of a location search using a
    model which has a Cell-like set of fields.

    .. attribute:: model

        A model which has a Cell interface to be used
        in the location search.
    """
    model = None
    data_field = 'cell'
    log_name = 'cell'
    location_type = PositionLocation

    def _clean_cell_keys(self, data):
        """Pre-process cell data."""
        radio = data.get('radio')
        cell_keys = []
        for cell in data.get(self.data_field, ()):
            cell = CellLookup.validate(cell, default_radio=radio)
            if cell:
                cell_key = CellLookup.to_hashkey(cell)
                cell_keys.append(cell_key)

        return cell_keys

    def _query_database(self, cell_keys):
        """Query the cell model."""
        queried_cells = None

        load_fields = (
            'radio', 'mcc', 'mnc', 'lac', 'lat', 'lon', 'range')

        # only do a query if we have cell locations, or this will match
        # all rows in the table
        query = (self.model.querykeys(self.db_source, cell_keys)
                           .options(load_only(*load_fields))
                           .filter(self.model.lat.isnot(None))
                           .filter(self.model.lon.isnot(None)))

        try:
            queried_cells = query.all()
        except Exception:
            self.raven_client.captureException()

        if queried_cells:
            return self._filter_cells(queried_cells)

    def _filter_cells(self, found_cells):
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

        return [Network(
            key=None,
            lat=cell.lat,
            lon=cell.lon,
            range=cell.range,
        ) for cell in lac[0]]

    def _prepare_location(self, queried_cells):  # pragma: no cover
        """
        Combine the queried_cells into an estimated location.

        :rtype: :class:`~ichnaea.locate.Location`
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
                location = self._prepare_location(queried_cells)
        return location


class CellLocationProvider(CellLocationProvider):
    """
    A CellLocationProvider implements a cell location search using
    the Cell model.
    """
    model = Cell


class OCIDCellLocationProvider(CellLocationProvider):
    """
    A CellLocationProvider implements a cell location search using
    the OCID Cell model.
    """
    model = OCIDCell
    source = DataSource.OCID


class CellAreaLocationProvider(CellLocationProvider):

    def _prepare_location(self, queried_cells):
        # take the smallest LAC of any the user is inside
        lac = sorted(queried_cells, key=operator.attrgetter('range'))[0]
        accuracy = float(max(LAC_MIN_ACCURACY, lac.range))
        return self.location_type(lat=lac.lat, lon=lac.lon, accuracy=accuracy)


class CellAreaLocationProvider(CellAreaLocationProvider):
    """
    A CellAreaLocationProvider implements a cell location search
    using the CellArea model.
    """
    model = CellArea
    log_name = 'cell_lac'


class OCIDCellAreaLocationProvider(CellAreaLocationProvider):
    """
    An OCIDCellAreaLocationProvider implements a cell location search
    using the OCIDCellArea model.
    """
    model = OCIDCellArea
    log_name = 'cell_lac'
    source = DataSource.OCID


class CellCountryProvider(CellLocationProvider):
    """
    A CellCountryProvider implements a cell country search without
    using any DB models.
    """
    location_type = CountryLocation

    def _query_database(self, cell_keys):
        countries = []
        for key in cell_keys:
            countries.extend(mobile_codes.mcc(str(key.mcc)))
        if len(set([c.alpha2 for c in countries])) != 1:
            # refuse to guess country if there are multiple choices
            return []
        return countries[0]

    def _prepare_location(self, obj):
        return self.location_type(country_code=obj.alpha2,
                                  country_name=obj.name)


class WifiLocationProvider(LocationProvider):
    """
    A WifiLocationProvider implements a location search using
    the WiFi models and a series of clustering algorithms.
    """
    data_field = 'wifi'
    log_name = 'wifi'
    location_type = PositionLocation

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
        queried_wifis = []
        if len(wifi_keys) >= MIN_WIFIS_IN_QUERY:
            keys = [Wifi.to_hashkey(key=key) for key in wifi_keys]
            try:
                load_fields = ('key', 'lat', 'lon', 'range')
                query = (Wifi.querykeys(self.db_source, keys)
                             .options(load_only(*load_fields))
                             .filter(Wifi.lat.isnot(None))
                             .filter(Wifi.lon.isnot(None)))
                queried_wifis = query.all()
            except Exception:
                self.raven_client.captureException()

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

    def _prepare_location(self, clusters):
        clusters.sort(lambda a, b: cmp(len(b), len(a)))
        cluster = clusters[0]
        sample = cluster[:min(len(cluster), MAX_WIFIS_IN_CLUSTER)]
        length = len(sample)
        avg_lat = sum([n.lat for n in sample]) / length
        avg_lon = sum([n.lon for n in sample]) / length
        accuracy = self._estimate_accuracy(avg_lat, avg_lon,
                                           sample, WIFI_MIN_ACCURACY)
        return self.location_type(lat=avg_lat, lon=avg_lon, accuracy=accuracy)

    def sufficient_data(self, wifi_keys):
        return (len(self.filter_bssids_by_similarity(list(wifi_keys))) >=
                MIN_WIFIS_IN_QUERY)

    def locate(self, data):
        location = self.location_type(query_data=False)

        wifis, wifi_signals, wifi_keys = self.get_clean_wifi_keys(data)

        if len(wifi_keys) < MIN_WIFIS_IN_QUERY:
            # We didn't get enough keys.
            if len(wifi_keys) >= 1:
                self.stat_count('wifi.provided_too_few')
        else:
            self.stat_time('wifi.provided', len(wifi_keys))

            if self.sufficient_data(wifi_keys):
                location.query_data = True

            queried_wifis = self._query_database(wifi_keys)

            if len(queried_wifis) < len(wifi_keys):
                self.stat_count('wifi.partial_match')
                self.stats_client.timing(
                    '{api}.wifi.provided_not_known'.format(api=self.api_name),
                    len(wifi_keys) - len(queried_wifis))

            clusters = self.get_clusters(wifi_signals, queried_wifis)

            if len(clusters) == 0:
                self.stat_count('wifi.found_no_cluster')
            else:
                location = self._prepare_location(clusters)

        return location


class GeoIPLocationProvider(LocationProvider):
    """
    A GeoIPLocationProvider implements a location search using a
    GeoIP client service lookup.
    """
    db_source_field = 'geoip'
    data_field = 'geoip'
    log_name = 'geoip'
    source = DataSource.GeoIP

    def locate(self, data):
        """Provide a location given the provided client IP address.

        :rtype: :class:`~ichnaea.locate.Location`
        """
        # Always consider there to be GeoIP data, even if no client_addr
        # was provided
        location = self.location_type(query_data=True)
        client_addr = data.get(self.data_field, None)

        if client_addr and self.db_source is not None:
            geoip = self.db_source.geoip_lookup(client_addr)
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


class PositionGeoIPLocationProvider(GeoIPLocationProvider):
    location_type = PositionLocation


class CountryGeoIPLocationProvider(GeoIPLocationProvider):
    location_type = CountryLocation
