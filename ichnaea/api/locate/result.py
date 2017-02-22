"""
Classes representing an abstract query result or
a concrete position or region result.
"""

from collections import defaultdict
import operator

from ichnaea.api.locate.constants import DataAccuracy
from ichnaea.constants import DEGREE_DECIMAL_PLACES
from ichnaea.geocalc import distance


class Result(object):
    """An abstract query result."""

    _repr_fields = ()  #: The list of important attributes.

    def __init__(self, accuracy=None, region_code=None, region_name=None,
                 fallback=None, lat=None, lon=None, source=None, score=0.0,
                 used_networks=None):
        self.accuracy = self._round(accuracy)
        self.fallback = fallback
        self.lat = self._round(lat)
        self.lon = self._round(lon)
        self.region_code = region_code
        self.region_name = region_name
        self.score = score
        self.source = source
        self.used_networks = used_networks if used_networks else []

    def __repr__(self):
        values = []
        for field in self._repr_fields:
            values.append('%s:%s' % (field, getattr(self, field, '')))
        return '{klass}<{values}>'.format(
            klass=self.__class__.__name__,
            values=', '.join(values),
        )

    def _round(self, value):
        if value is not None:
            value = round(value, DEGREE_DECIMAL_PLACES)
        return value

    @property
    def data_accuracy(self):
        """Return the accuracy class of this result."""
        if self.accuracy is None:
            return DataAccuracy.none
        return DataAccuracy.from_number(self.accuracy)


class Position(Result):
    """The position returned by a position query."""

    _repr_fields = ('lat', 'lon',
                    'accuracy', 'score',
                    'fallback', 'source')  #:

    def json(self):
        if self.lat is None or self.lon is None or self.accuracy is None:
            return {'position': {'source': 'query'}}

        return {'position': {
            'latitude': self.lat,
            'longitude': self.lon,
            'accuracy': self.accuracy,
            'source': 'query',
        }}


class Region(Result):
    """The region returned by a region query."""

    _repr_fields = ('region_code', 'region_name',
                    'accuracy', 'score',
                    'fallback', 'source')  #:


class ResultList(object):
    """An abstract collection of query results."""

    result_type = None  #:

    def __init__(self, result=None):
        self._results = []
        if result is not None:
            self.add(result)

    def add(self, results):
        """Add one or more results to the collection."""
        if isinstance(results, Result):
            self._results.append(results)
        else:
            self._results.extend(list(results))

    def __getitem__(self, index):
        return self._results[index]

    def __len__(self):
        return len(self._results)

    def __repr__(self):
        return '%s: %s' % (
            self.__class__.__name__,
            ', '.join([repr(res) for res in self]))

    def best_cluster(self):
        """Return the best cluster from this collection."""
        raise NotImplementedError()

    def best(self):
        """Return the best result in the collection."""
        raise NotImplementedError()

    def satisfies(self, query):
        """
        Is the best cluster result from this collection good enough to
        satisfy the query?
        """
        raise NotImplementedError()


class PositionResultList(ResultList):
    """A collection of position results."""

    result_type = Position  #:

    def best_cluster(self):
        """Return the best cluster from this collection."""
        if len(self) <= 1:
            return self

        results = sorted(self, key=operator.attrgetter('accuracy'))

        clusters = {}
        for i, result1 in enumerate(results):
            clusters[i] = [result1]
            # allow a 50% buffer zone around each result
            radius1 = result1.accuracy * 1.5
            for j, result2 in enumerate(results):
                if j > i:
                    # only calculate the upper triangle
                    radius2 = result2.accuracy * 1.5
                    max_radius = max(radius1, radius2)
                    apart = distance(result1.lat, result1.lon,
                                     result2.lat, result2.lon)
                    if apart <= max_radius:
                        clusters[i].append(result2)

        def sum_score(values):
            # Sort by highest cumulative score,
            # break tie by highest individual score
            return (sum([v.score for v in values]),
                    max([v.score for v in values]))

        clusters = sorted(clusters.values(), key=sum_score, reverse=True)
        return clusters[0]

    def best(self):
        """Return the best result in the collection."""
        best_cluster = self.best_cluster()
        if len(best_cluster) == 0:
            return None
        if len(best_cluster) == 1:
            return best_cluster[0]

        def best_result(result):
            # sort descending, take smallest accuracy/radius,
            # break tie by higher score
            return ((result.accuracy or 0.0), result.score * -1.0)

        sorted_results = sorted(best_cluster, key=best_result)
        return sorted_results[0]

    def satisfies(self, query):
        """
        Is the best cluster result from this collection good enough to
        satisfy the query?
        """
        cluster = self.best_cluster()
        if len(cluster) == 0:
            return False

        cluster_score = sum([res.score for res in cluster])
        cluster_accuracy = min([res.data_accuracy for res in cluster])

        if (cluster_score >= 1.0 and
                cluster_accuracy <= query.expected_accuracy):
            return True
        return False


class RegionResultList(ResultList):
    """A collection of region results."""

    result_type = Region  #:

    def best_cluster(self):
        """Return the best cluster from this collection."""
        if len(self) <= 1:
            return self

        # Group by region code
        clusters = defaultdict(list)
        for result in self:
            clusters[result.region_code].append(result)

        def sum_score(values):
            # Sort by highest cumulative score,
            # break tie by region with the largest radius.
            return (sum([v.score for v in values]),
                    max([v.accuracy for v in values]))

        clusters = sorted(clusters.values(), key=sum_score, reverse=True)
        return clusters[0]

    def best(self):
        """Return the best result in the collection."""
        best_cluster = self.best_cluster()
        if len(best_cluster) == 0:
            return None
        if len(best_cluster) == 1:
            return best_cluster[0]

        def best_result(result):
            # sort ascending, take smallest source first,
            # break tie by higher score
            return ((result.source.value), result.score * -1.0)

        sorted_results = sorted(best_cluster, key=best_result)
        return sorted_results[0]

    def satisfies(self, query):
        """
        Is the best cluster result from this collection good enough to
        satisfy the query?
        """
        if len(self) > 0:
            return True
        return False
