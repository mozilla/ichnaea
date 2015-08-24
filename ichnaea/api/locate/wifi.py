"""Search implementation using a wifi database."""

from collections import defaultdict, namedtuple
from operator import attrgetter

import numpy
from sqlalchemy.orm import load_only
from sqlalchemy.sql import or_

from ichnaea.api.locate.constants import (
    DataSource,
    MAX_WIFI_CLUSTER_METERS,
    MIN_WIFIS_IN_CLUSTER,
    MAX_WIFIS_IN_CLUSTER,
)
from ichnaea.api.locate.result import Position
from ichnaea.api.locate.source import PositionSource
from ichnaea.constants import (
    PERMANENT_BLOCKLIST_THRESHOLD,
    TEMPORARY_BLOCKLIST_DURATION,
    WIFI_MIN_ACCURACY,
)
from ichnaea.geocalc import (
    aggregate_position,
    distance,
)
from ichnaea.models import (
    Wifi,
    WifiShard,
)
from ichnaea import util

Network = namedtuple('Network', 'key lat lon radius signal')


def cluster_elements(items, distance_fn, threshold):
    """
    Generic pairwise clustering routine.

    :param items: A list of elements to cluster.
    :param distance_fn: A pairwise distance function over elements.
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


def filter_bssids_by_similarity(bssids, distance_threshold=2):
    """
    Cluster BSSIDs by "similarity" (hamming or arithmetic distance);
    return one BSSID from each cluster. The distance threshold is
    hard-wired to 2, meaning that two BSSIDs are clustered together
    if they are within a numeric difference of 2 of one another or
    a hamming distance of 2.
    """

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

    clusters = cluster_elements(
        bssids, bssid_difference, distance_threshold)
    return [cluster[0] for cluster in clusters]


def get_clusters(wifis, lookups):
    """
    Given a list of wifi models and wifi lookups, return
    a list of clusters of nearby wifi networks.
    """

    # Filter out BSSIDs that are numerically very similar, assuming
    # they are multiple interfaces on the same base station or such.
    dissimilar_macs = set(filter_bssids_by_similarity([w.mac for w in wifis]))

    # Create a dict of wifi keys mapped to their signal strength.
    # Estimate signal strength at -100 dBm if none is provided,
    # which is worse than the 99th percentile of wifi dBms we
    # see in practice (-98).
    wifi_signals = {}
    for lookup in lookups:
        if lookup.mac in dissimilar_macs:
            wifi_signals[lookup.mac] = lookup.signal or -100

    wifi_networks = [
        Network(w.mac, w.lat, w.lon, w.radius, wifi_signals[w.mac])
        for w in wifis if w.mac in dissimilar_macs]

    # Sort networks by signal strengths in query.
    wifi_networks.sort(key=attrgetter('signal'), reverse=True)

    def wifi_distance(one, two):
        return distance(one.lat, one.lon, two.lat, two.lon)

    clusters = cluster_elements(
        wifi_networks, wifi_distance, MAX_WIFI_CLUSTER_METERS)

    # Only consider clusters that have at least 2 found networks
    # inside them. Otherwise someone could use a combination of
    # one real network and one fake and therefor not found network to
    # get the position of the real network.
    return [c for c in clusters if len(c) >= MIN_WIFIS_IN_CLUSTER]


def pick_best_cluster(clusters):
    """
    Out of the list of possible clusters, pick the best one.

    Currently we pick the cluster with the most found networks inside
    it. If we find more than one cluster, we have some stale data in
    our database, as a device shouldn't be able to pick up signals
    from networks more than
    :data:`ichnaea.api.locate.constants.MAX_WIFI_CLUSTER_METERS` apart.
    We assume that the majority of our data is correct and discard the
    minority match.

    The list of clusters is pre-sorted by signal strength, so given
    two clusters with two networks each, the cluster with the better
    signal strength readings wins.
    """
    def sort_cluster(cluster):
        return len(cluster)

    return sorted(clusters, key=sort_cluster, reverse=True)[0]


def aggregate_cluster_position(cluster, result_type):
    """
    Given a single cluster, return the aggregate position of the user
    inside the cluster.

    We take at most
    :data:`ichnaea.api.locate.constants.MAX_WIFIS_IN_CLUSTER`
    of of the networks in the cluster when estimating the aggregate
    position.

    The reason is that we're doing a (non-weighted) centroid calculation,
    which is itself unbalanced by distant elements. Even if we did a
    weighted centroid here, using radio intensity as a proxy for
    distance has an error that increases significantly with distance,
    so we'd have to underweight pretty heavily.
    """
    sample = cluster[:min(len(cluster), MAX_WIFIS_IN_CLUSTER)]
    circles = numpy.array(
        [(wifi.lat, wifi.lon, wifi.radius) for wifi in sample],
        dtype=numpy.float64)
    lat, lon, accuracy = aggregate_position(circles, WIFI_MIN_ACCURACY)
    return result_type(lat=lat, lon=lon, accuracy=accuracy)


def query_database(query, raven_client):
    macs = dict([(lookup.mac, None) for lookup in query.wifi])
    if not macs:  # pragma: no cover
        return []

    today = util.utcnow().date()
    temp_blocked = today - TEMPORARY_BLOCKLIST_DURATION

    try:
        load_fields = ('lat', 'lon', 'radius')
        shards = defaultdict(list)
        for mac in macs.keys():
            shards[WifiShard.shard_model(mac)].append(mac)

        for shard, shard_macs in shards.items():
            results = (
                query.session.query(shard)
                             .filter(shard.mac.in_(shard_macs))
                             .filter(shard.lat.isnot(None))
                             .filter(shard.lon.isnot(None))
                             .filter(or_(
                                 shard.block_count.is_(None),
                                 shard.block_count <
                                     PERMANENT_BLOCKLIST_THRESHOLD))
                             .filter(or_(
                                 shard.block_last.is_(None),
                                 shard.block_last < temp_blocked))
                             .options(load_only(*load_fields))
            ).all()
            for result in results:
                macs[result.mac] = result

        # Limit the query to the not found networks
        not_found_macs = [mac for mac, value in macs.items() if value is None]

        # Load the extra key field, as its not the actual primary key
        load_fields = ('key', 'lat', 'lon', 'range')
        results = (
            query.session.query(Wifi)
                         .filter(Wifi.key.in_(not_found_macs))
                         .filter(Wifi.lat.isnot(None))
                         .filter(Wifi.lon.isnot(None))
                         .options(load_only(*load_fields))
        ).all()
        for result in results:
            macs[result.key] = result

        return [value for value in macs.values() if value is not None]
    except Exception:
        raven_client.captureException()
    return []


class WifiPositionMixin(object):
    """
    A WifiPositionMixin implements a position search using
    the WiFi models and a series of clustering algorithms.
    """

    raven_client = None
    result_type = Position

    def should_search_wifi(self, query, results):
        return bool(query.wifi)

    def search_wifi(self, query):
        result = self.result_type()
        if not query.wifi:
            return result

        wifis = query_database(query, self.raven_client)
        clusters = get_clusters(wifis, query.wifi)
        if clusters:
            cluster = pick_best_cluster(clusters)
            result = aggregate_cluster_position(cluster, self.result_type)

        return result


class WifiPositionSource(WifiPositionMixin, PositionSource):
    """
    Implements a search using our wifi data.

    This source is only used in tests.
    """

    fallback_field = None  #:
    source = DataSource.internal

    def should_search(self, query, results):
        return self.should_search_wifi(query, results)

    def search(self, query):
        return self.search_wifi(query)
