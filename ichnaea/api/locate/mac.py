"""Search implementation using a mac based source."""

from collections import defaultdict
import itertools

import numpy
from scipy.cluster import hierarchy
from sqlalchemy.orm import load_only
from sqlalchemy.sql import or_

from ichnaea.constants import (
    PERMANENT_BLOCKLIST_THRESHOLD,
    TEMPORARY_BLOCKLIST_DURATION,
)
from ichnaea.geocalc import (
    aggregate_position,
    distance,
)
from ichnaea import util

NETWORK_DTYPE = numpy.dtype([
    ('lat', numpy.double),
    ('lon', numpy.double),
    ('radius', numpy.double),
    ('signal', numpy.int32),
    ('score', numpy.double),
])


def cluster_networks(models, lookups, min_signal=None, max_distance=None):
    """
    Given a list of database models and lookups, return
    a list of clusters of nearby networks.
    """
    now = util.utcnow()

    # Create a dict of macs mapped to their signal strength.
    signals = {}
    for lookup in lookups:
        signals[lookup.mac] = lookup.signal or min_signal

    networks = numpy.array(
        [(model.lat, model.lon, model.radius,
          signals[model.mac], model.score(now))
         for model in models],
        dtype=NETWORK_DTYPE)

    # Only consider clusters that have at least 2 found networks
    # inside them. Otherwise someone could use a combination of
    # one real network and one fake and therefor not found network to
    # get the position of the real network.
    length = len(networks)
    if length < 2:
        # Not enough networks to form a valid cluster.
        return []

    positions = networks[['lat', 'lon']]
    if length == 2:
        one = positions[0]
        two = positions[1]
        if distance(one[0], one[1],
                    two[0], two[1]) <= max_distance:
            # Only two networks and they agree, so cluster them.
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
        link_matrix, max_distance, criterion='distance', depth=2)

    indexed_clusters = defaultdict(list)
    for i, net in zip(assignments, networks):
        indexed_clusters[i].append(net)

    clusters = []
    for values in indexed_clusters.values():
        if len(values) >= 2:
            clusters.append(numpy.array(values, dtype=NETWORK_DTYPE))

    return clusters


def aggregate_cluster_position(cluster, result_type, max_networks=None,
                               min_accuracy=None, max_accuracy=None):
    """
    Given a single cluster, return the aggregate position of the user
    inside the cluster.
    """
    # Reverse sort by signal, to pick the best sample of networks.
    cluster.sort(order='signal')
    cluster = numpy.flipud(cluster)

    sample = cluster[:min(len(cluster), max_networks)]
    circles = numpy.array(
        [(net[0], net[1], net[2])
         for net in sample[['lat', 'lon', 'radius']]],
        dtype=numpy.double)

    lat, lon, accuracy = aggregate_position(circles, min_accuracy)
    accuracy = min(accuracy, max_accuracy)
    score = float(cluster['score'].sum())
    return result_type(lat=lat, lon=lon, accuracy=accuracy, score=score)


def query_macs(query, lookups, raven_client, db_model):
    macs = [lookup.mac for lookup in lookups]
    if not macs:  # pragma: no cover
        return []

    result = []
    today = util.utcnow().date()
    temp_blocked = today - TEMPORARY_BLOCKLIST_DURATION

    try:
        # load all fields used in score calculation and those we
        # need for the position or region
        load_fields = ('lat', 'lon', 'radius', 'region', 'samples',
                       'created', 'modified', 'last_seen', 'block_last')
        shards = defaultdict(list)
        for mac in macs:
            shards[db_model.shard_model(mac)].append(mac)

        for shard, shard_macs in shards.items():
            rows = (
                query.session.query(shard)
                             .filter(shard.mac.in_(shard_macs),
                                     shard.lat.isnot(None),
                                     shard.lon.isnot(None),
                                     or_(shard.block_count.is_(None),
                                         shard.block_count <
                                         PERMANENT_BLOCKLIST_THRESHOLD),
                                     or_(shard.block_last.is_(None),
                                         shard.block_last < temp_blocked))
                             .options(load_only(*load_fields))
            ).all()
            result.extend(list(rows))
    except Exception:
        raven_client.captureException()
    return result
