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
    """An empty query result."""

    _required = ()  #: The list of required attributes.

    def __init__(self, accuracy=None, region_code=None, region_name=None,
                 fallback=None, lat=None, lon=None, source=None, score=0.0):
        self.accuracy = self._round(accuracy)
        self.fallback = fallback
        self.lat = self._round(lat)
        self.lon = self._round(lon)
        self.region_code = region_code
        self.region_name = region_name
        self.score = score
        self.source = source

    def __repr__(self):
        values = []
        for field in self._required:
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
        if self.empty():
            return DataAccuracy.none
        return DataAccuracy.from_number(self.accuracy)

    def empty(self):
        """Does this result include any data?"""
        if not self._required:
            return True
        all_fields = []
        for field in self._required:
            all_fields.append(getattr(self, field, None))
        return None in all_fields

    def as_list(self):
        """Return a new result list including this result."""
        raise NotImplementedError()

    def new_list(self):
        """Return a new empty result list."""
        raise NotImplementedError()


class Position(Result):
    """The position returned by a position query."""

    _required = ('lat', 'lon', 'accuracy', 'score')  #:

    def as_list(self):
        """Return a new position result list including this result."""
        return PositionResultList(self)

    def new_list(self):
        """Return a new empty result list."""
        return PositionResultList()


class Region(Result):
    """The region returned by a region query."""

    _required = ('region_code', 'region_name', 'accuracy', 'score')  #:

    def as_list(self):
        """Return a new region result list including this result."""
        return RegionResultList(self)

    def new_list(self):
        """Return a new empty result list."""
        return RegionResultList()


class ResultList(object):
    """A collection of query results."""

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
        return 'ResultList: %s' % ', '.join([repr(res) for res in self])

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
        if len(self) == 0:
            return self.result_type().as_list()
        if len(self) == 1:
            return self
        not_empty = [res for res in self if not res.empty()]
        if len(not_empty) == 0:
            return self[0].as_list()
        if len(not_empty) == 1:
            return not_empty

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
        cluster_score = sum([res.score for res in cluster])
        cluster_accuracy = min([res.data_accuracy for res in cluster])

        if (cluster_score >= 1.0 and
                cluster_accuracy <= query.expected_accuracy):
            return True
        return False


class RegionResultList(ResultList):
    """A collection of region results."""

    result_type = Region  #:

    def best(self):
        """Return the best result in the collection."""
        # group by region code
        grouped = defaultdict(list)
        for result in self:
            if not result.empty():
                grouped[result.region_code].append(result)

        regions = []
        for code, values in grouped.items():
            # Pick the first found value, this determines the source
            # and possible fallback flag on the end result.
            region = values[0]
            regions.append((
                sum([value.score for value in values]),
                region.accuracy,
                region))

        if not regions:
            return self.result_type()

        # pick the region with the highest combined score,
        # break tie by region with the largest radius
        sorted_regions = sorted(regions, reverse=True)
        return sorted_regions[0][2]

    def satisfies(self, query):
        """
        Is the best cluster result from this collection good enough to
        satisfy the query?
        """
        for result in self:
            if not result.empty():
                return True
        return False
