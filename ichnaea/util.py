from datetime import datetime
from pytz import UTC


def utcnow():
    return datetime.utcnow().replace(microsecond=0, tzinfo=UTC)


def cluster_elements(elts, dist, thresh):
    """
    Generic pairwise clustering routine.

    Arguments:

    elts -- a list of elemenets to cluster
    dist -- a pairwise distance function over elements

    thresh -- be a numeric threshold for clustering;
              clusters P, Q will be joined if dist(a,b) <= thresh,
              for any a in P, b in Q.

    Returns: list of lists of elements, each sub-list being a cluster.
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
