"""Search implementation using a wifi database."""

from collections import defaultdict
import itertools

import numpy
from scipy.cluster import hierarchy
from sqlalchemy.orm import load_only
from sqlalchemy.sql import or_

from ichnaea.api.locate.constants import (
    DataSource,
    MAX_WIFI_CLUSTER_METERS,
    MIN_WIFIS_IN_CLUSTER,
    MAX_WIFIS_IN_CLUSTER,
    WIFI_MAX_ACCURACY,
    WIFI_MIN_ACCURACY,
)
from ichnaea.api.locate.result import (
    Position,
    Region,
)
from ichnaea.api.locate.source import PositionSource
from ichnaea.constants import (
    PERMANENT_BLOCKLIST_THRESHOLD,
    TEMPORARY_BLOCKLIST_DURATION,
)
from ichnaea.geocalc import (
    aggregate_position,
    distance,
)
from ichnaea.geocode import GEOCODER
from ichnaea.models import WifiShard
from ichnaea import util

NETWORK_DTYPE = numpy.dtype([
    ('mac', numpy.unicode_, 12),
    ('lat', numpy.double),
    ('lon', numpy.double),
    ('radius', numpy.double),
    ('signal', numpy.int32),
    ('score', numpy.double),
])


def cluster_wifis(networks):
    # Only consider clusters that have at least 2 found networks
    # inside them. Otherwise someone could use a combination of
    # one real network and one fake and therefor not found network to
    # get the position of the real network.
    length = len(networks)
    if length < MIN_WIFIS_IN_CLUSTER:
        # Not enough WiFis to form a valid cluster.
        return []

    positions = networks[['lat', 'lon']]
    if length == 2:
        one = positions[0]
        two = positions[1]
        if distance(one[0], one[1],
                    two[0], two[1]) <= MAX_WIFI_CLUSTER_METERS:
            # Only two WiFis and they agree, so cluster them.
            return [networks]
        else:
            # Or they disagree forming two clusters of size one,
            # neither of which is large enough to be returned.
            return []

    # Calculate the condensed distance matrix based on distance in meters.
    # This avoids calculating the square form, which would calculate
    # each value twice and avoids calculating the diagonal of zeros.
    # We avoid the special cases for length < 2 with the above checks.
    # See scipy.spatial.distance.squareform and
    # https://stackoverflow.com/questions/13079563
    dist_matrix = numpy.zeros(length * (length - 1) // 2, dtype=numpy.double)
    for i, (a, b) in enumerate(itertools.combinations(positions, 2)):
        dist_matrix[i] = distance(a[0], a[1], b[0], b[1])

    link_matrix = hierarchy.linkage(dist_matrix, method='complete')
    assignments = hierarchy.fcluster(
        link_matrix, MAX_WIFI_CLUSTER_METERS, criterion='distance', depth=2)

    indexed_clusters = defaultdict(list)
    for i, net in zip(assignments, networks):
        indexed_clusters[i].append(net)

    clusters = []
    for values in indexed_clusters.values():
        if len(values) >= MIN_WIFIS_IN_CLUSTER:
            clusters.append(numpy.array(values, dtype=NETWORK_DTYPE))

    return clusters


def get_clusters(wifis, lookups):
    """
    Given a list of wifi models and wifi lookups, return
    a list of clusters of nearby wifi networks.
    """
    now = util.utcnow()

    # Create a dict of WiFi macs mapped to their signal strength.
    # Estimate signal strength at -100 dBm if none is provided,
    # which is worse than the 99th percentile of wifi dBms we
    # see in practice (-98).
    signals = {}
    for lookup in lookups:
        signals[lookup.mac] = lookup.signal or -100

    networks = numpy.array(
        [(wifi.mac, wifi.lat, wifi.lon, wifi.radius,
          signals[wifi.mac], wifi.score(now))
         for wifi in wifis],
        dtype=NETWORK_DTYPE)

    return cluster_wifis(networks)


def pick_best_cluster(clusters):
    """
    Out of the list of possible clusters, pick the best one based
    on the sum of the individual network scores.

    In case of a tie, we use the cluster with the better median
    signal strength.
    """

    def sort_cluster(cluster):
        return (cluster['score'].sum(),
                numpy.median(cluster['signal']))

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
    # Reverse sort by signal, to pick the best sample of networks.
    cluster.sort(order='signal')
    cluster = numpy.flipud(cluster)
    score = float(cluster['score'].sum())

    sample = cluster[:min(len(cluster), MAX_WIFIS_IN_CLUSTER)]
    circles = numpy.array(
        [(net[0], net[1], net[2])
         for net in sample[['lat', 'lon', 'radius']]],
        dtype=numpy.double)
    lat, lon, accuracy = aggregate_position(circles, WIFI_MIN_ACCURACY)
    accuracy = min(accuracy, WIFI_MAX_ACCURACY)
    return result_type(lat=lat, lon=lon, accuracy=accuracy, score=score)


def query_wifis(query, raven_client):
    macs = [lookup.mac for lookup in query.wifi]
    if not macs:  # pragma: no cover
        return []

    result = []
    today = util.utcnow().date()
    temp_blocked = today - TEMPORARY_BLOCKLIST_DURATION

    try:
        # load all fields used in score calculation and those we
        # need for the position or region
        load_fields = ('lat', 'lon', 'radius', 'region',
                       'created', 'modified', 'samples')
        shards = defaultdict(list)
        for mac in macs:
            shards[WifiShard.shard_model(mac)].append(mac)

        for shard, shard_macs in shards.items():
            rows = (
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
            result.extend(list(rows))
    except Exception:
        raven_client.captureException()
    return result


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
        results = self.result_type().new_list()

        wifis = query_wifis(query, self.raven_client)
        clusters = get_clusters(wifis, query.wifi)
        if clusters:
            cluster = pick_best_cluster(clusters)
            results.add(aggregate_cluster_position(cluster, self.result_type))

        return results


class WifiRegionMixin(object):
    """
    A WifiRegionMixin implements a region search using our wifi data.
    """

    raven_client = None
    result_type = Region

    def should_search_wifi(self, query, results):
        return bool(query.wifi)

    def search_wifi(self, query):
        results = self.result_type().new_list()

        now = util.utcnow()
        regions = defaultdict(int)
        wifis = query_wifis(query, self.raven_client)
        for wifi in wifis:
            regions[wifi.region] += wifi.score(now)

        for code, score in regions.items():
            region = GEOCODER.region_for_code(code)
            if region:
                results.add(self.result_type(
                    region_code=code,
                    region_name=region.name,
                    accuracy=region.radius,
                    score=score))

        return results


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
