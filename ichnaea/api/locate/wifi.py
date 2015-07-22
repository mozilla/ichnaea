"""Implementation of a search provider using a wifi database."""

from sqlalchemy.orm import load_only

from ichnaea.api.locate.constants import (
    MAX_WIFI_CLUSTER_KM,
    MIN_WIFIS_IN_QUERY,
    MIN_WIFIS_IN_CLUSTER,
    MAX_WIFIS_IN_CLUSTER,
)
from ichnaea.api.locate.provider import (
    Network,
    Provider,
)
from ichnaea.api.locate.result import Position
from ichnaea.constants import WIFI_MIN_ACCURACY
from ichnaea.geocalc import (
    distance,
    estimate_accuracy,
)
from ichnaea.models import Wifi


class WifiPositionProvider(Provider):
    """
    A WifiPositionProvider implements a position search using
    the WiFi models and a series of clustering algorithms.
    """

    result_type = Position

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

    def _get_clean_wifi_keys(self, query):
        wifis = query.wifi

        # Estimate signal strength at -100 dBm if none is provided,
        # which is worse than the 99th percentile of wifi dBms we
        # see in practice (-98).

        wifi_signals = dict([(w.key, w.signal or -100) for w in wifis])
        wifi_keys = set(wifi_signals.keys())

        return (wifis, wifi_signals, wifi_keys)

    def _query_database(self, query, wifi_keys):
        try:
            load_fields = ('key', 'lat', 'lon', 'range')
            wifi_iter = Wifi.iterkeys(
                query.session,
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
        # The reason we take a subset of those points when estimating a
        # position is that we're doing a (non-weighted) centroid calculation,
        # which is itself unbalanced by distant elements. Even if we did a
        # weighted centroid here, using radio intensity as a proxy for
        # distance has an error that increases significantly with distance,
        # so we'd have to underweight pretty heavily.

        return [c for c in clusters if len(c) >= MIN_WIFIS_IN_CLUSTER]

    def _prepare(self, clusters):
        clusters.sort(key=lambda a: len(a), reverse=True)
        cluster = clusters[0]
        sample = cluster[:min(len(cluster), MAX_WIFIS_IN_CLUSTER)]
        length = len(sample)
        avg_lat = sum([n.lat for n in sample]) / length
        avg_lon = sum([n.lon for n in sample]) / length
        accuracy = estimate_accuracy(avg_lat, avg_lon,
                                     sample, WIFI_MIN_ACCURACY)
        return self.result_type(lat=avg_lat, lon=avg_lon, accuracy=accuracy)

    def search(self, query):
        result = self.result_type()

        wifis, wifi_signals, wifi_keys = self._get_clean_wifi_keys(query)

        if len(wifi_keys) >= MIN_WIFIS_IN_QUERY:
            queried_wifis = self._query_database(query, wifi_keys)
            clusters = self._get_clusters(wifi_signals, queried_wifis)

            if clusters:
                result = self._prepare(clusters)

        return result
