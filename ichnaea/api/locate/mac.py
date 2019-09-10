"""Search implementation using a mac based source."""

from collections import defaultdict
import itertools
import math

import numpy
from scipy.cluster import hierarchy
from scipy.optimize import leastsq
from sqlalchemy import select

from geocalc import distance
from ichnaea.api.locate.score import station_score
from ichnaea.models import decode_mac, encode_mac, station_blocked
from ichnaea import util

NETWORK_DTYPE = numpy.dtype(
    [
        ("lat", numpy.double),
        ("lon", numpy.double),
        ("radius", numpy.double),
        ("age", numpy.int32),
        ("signalStrength", numpy.int32),
        ("score", numpy.double),
        ("mac", "S6"),
        ("seen_today", numpy.bool),
    ]
)


def cluster_networks(
    models, lookups, min_age=0, min_radius=None, min_signal=None, max_distance=None
):
    """
    Given a list of database models and lookups, return
    a list of clusters of nearby networks.
    """
    now = util.utcnow()
    today = now.date()

    # Create a dict of macs mapped to their age and signal strength.
    obs_data = {}
    for lookup in lookups:
        obs_data[decode_mac(lookup.mac)] = (
            max(abs(lookup.age or min_age), 1000),
            lookup.signalStrength or min_signal,
        )

    networks = numpy.array(
        [
            (
                model.lat,
                model.lon,
                model.radius or min_radius,
                obs_data[model.mac][0],
                obs_data[model.mac][1],
                station_score(model, now),
                encode_mac(model.mac),
                bool(model.last_seen >= today),
            )
            for model in models
        ],
        dtype=NETWORK_DTYPE,
    )

    # Only consider clusters that have at least 2 found networks
    # inside them. Otherwise someone could use a combination of
    # one real network and one fake and therefor not found network to
    # get the position of the real network.
    length = len(networks)
    if length < 2:
        # Not enough networks to form a valid cluster.
        return []

    positions = networks[["lat", "lon"]]
    if length == 2:
        one = positions[0]
        two = positions[1]
        if distance(one[0], one[1], two[0], two[1]) <= max_distance:
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

    link_matrix = hierarchy.linkage(dist_matrix, method="complete")
    assignments = hierarchy.fcluster(
        link_matrix, max_distance, criterion="distance", depth=2
    )

    indexed_clusters = defaultdict(list)
    for i, net in zip(assignments, networks):
        indexed_clusters[i].append(net)

    clusters = []
    for values in indexed_clusters.values():
        if len(values) >= 2:
            clusters.append(numpy.array(values, dtype=NETWORK_DTYPE))

    return clusters


def aggregate_mac_position(networks, minimum_accuracy):
    # Idea based on https://gis.stackexchange.com/questions/40660

    def func(point, points):
        return numpy.array(
            [
                distance(p["lat"], p["lon"], point[0], point[1])
                * min(math.sqrt(2000.0 / p["age"]), 1.0)
                / math.pow(p["signalStrength"], 2)
                for p in points
            ]
        )

    # Guess initial position as the weighted mean over all networks.
    points = numpy.array(
        [(net["lat"], net["lon"]) for net in networks], dtype=numpy.double
    )

    weights = numpy.array(
        [
            net["score"]
            * min(math.sqrt(2000.0 / net["age"]), 1.0)
            / math.pow(net["signalStrength"], 2)
            for net in networks
        ],
        dtype=numpy.double,
    )

    initial = numpy.average(points, axis=0, weights=weights)

    (lat, lon), cov_x, info, mesg, ier = leastsq(
        func, initial, args=networks, full_output=True
    )

    if ier not in (1, 2, 3, 4):  # pragma: no cover
        # No solution found, use initial estimate.
        lat, lon = initial

    # Guess the accuracy as the 95th percentile of the distances
    # from the lat/lon to the positions of all networks.
    distances = numpy.array(
        [distance(lat, lon, net["lat"], net["lon"]) for net in networks],
        dtype=numpy.double,
    )
    accuracy = max(numpy.percentile(distances, 95), minimum_accuracy)

    return (float(lat), float(lon), float(accuracy))


def aggregate_cluster_position(
    cluster,
    result_type,
    data_type,
    max_networks=None,
    min_accuracy=None,
    max_accuracy=None,
):
    """
    Given a single cluster, return the aggregate position of the user
    inside the cluster.
    """
    # Sort by score, to pick the best sample of networks.
    cluster.sort(order="score")
    sample = cluster[:max_networks]

    lat, lon, accuracy = aggregate_mac_position(sample, min_accuracy)
    accuracy = min(accuracy, max_accuracy)
    score = float(cluster["score"].sum())

    used_networks = [
        (data_type, bytes(mac), bool(seen_today))
        for mac, seen_today in sample[["mac", "seen_today"]]
    ]

    return result_type(
        lat=lat, lon=lon, accuracy=accuracy, score=score, used_networks=used_networks
    )


def query_macs(query, lookups, raven_client, db_model):
    macs = [lookup.mac for lookup in lookups]
    if not macs:  # pragma: no cover
        return []

    # load all fields used in score calculation and those we
    # need for the position or region
    load_fields = (
        "mac",
        "lat",
        "lon",
        "radius",
        "region",
        "samples",
        "created",
        "modified",
        "last_seen",
        "block_last",
        "block_count",
    )
    result = []
    today = util.utcnow().date()

    try:
        shards = defaultdict(list)
        for mac in macs:
            shards[db_model.shard_model(mac)].append(mac)

        for shard, shard_macs in shards.items():
            columns = shard.__table__.c
            fields = [getattr(columns, f) for f in load_fields]
            rows = (
                query.session.execute(
                    select(fields)
                    .where(columns.lat.isnot(None))
                    .where(columns.lon.isnot(None))
                    .where(columns.mac.in_(shard_macs))
                )
            ).fetchall()

            result.extend([row for row in rows if not station_blocked(row, today)])
    except Exception:
        raven_client.captureException()
    return result
