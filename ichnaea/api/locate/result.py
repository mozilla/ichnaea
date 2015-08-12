"""
Classes representing an abstract query result
or a concrete country or position result.
"""

from ichnaea.api.locate.constants import DataAccuracy
from ichnaea.constants import DEGREE_DECIMAL_PLACES
from ichnaea.geocalc import distance

try:
    from collections import OrderedDict
except ImportError:  # pragma: no cover
    from ordereddict import OrderedDict


class Result(object):
    """An empty query result."""

    _required = ()  #: The list of required attributes.

    def __init__(self, accuracy=None, country_code=None, country_name=None,
                 fallback=None, lat=None, lon=None, source=None):
        self.accuracy = self._round(accuracy)
        self.country_code = country_code
        self.country_name = country_name
        self.fallback = fallback
        self.lat = self._round(lat)
        self.lon = self._round(lon)
        self.source = source

    def __repr__(self):  # pragma: no cover
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
        return DataAccuracy.none

    def found(self):
        """Does this result include any data?"""
        if not self._required:
            return False
        for field in self._required:
            if getattr(self, field, None) is None:
                return False
        return True

    def agrees_with(self, other):
        """Does this result match the other result?"""
        return True

    def accurate_enough(self, query):
        """Is this result accurate enough to return it?"""
        return False

    def more_accurate(self, other):
        """Is this result better than the passed in result?"""
        return False


class ResultList(object):
    """A collection of query results."""

    def __init__(self, result=None):
        self._results = []
        if result is not None:
            self.add(result)

    def add(self, result):
        """Add one or more results to the collection."""
        if isinstance(result, Result):
            self._results.append(result)
        else:
            self._results.extend(list(result))

    def __len__(self):
        return len(self._results)

    def __getitem__(self, index):
        return self._results[index]

    def satisfies(self, query):
        """
        Is one of the results in the collection good enough to satisfy
        the expected query data accuracy.
        """
        for result in self:
            if result.accurate_enough(query):
                return True
        return False

    def best(self):
        """
        Return the best result in the collection.
        """
        accurate_results = OrderedDict()
        for result in self:
            accuracy = result.data_accuracy
            if accuracy in accurate_results:
                accurate_results[accuracy].append(result)
            else:
                accurate_results[accuracy] = [result]
        best_accuracy = min(accurate_results.keys())
        return accurate_results[best_accuracy][0]


class Position(Result):
    """The position returned by a position query."""

    _required = ('lat', 'lon', 'accuracy')  #:

    @property
    def data_accuracy(self):
        if self.accuracy is None:
            return DataAccuracy.none
        return DataAccuracy.from_number(self.accuracy)

    def agrees_with(self, other):
        dist = distance(other.lat, other.lon, self.lat, self.lon) * 1000
        return dist <= other.accuracy

    def accurate_enough(self, query):
        """
        We are accurate enough once we meet the expected query accuracy.
        """
        if self.data_accuracy <= query.expected_accuracy:
            return True
        return False

    def more_accurate(self, other):
        """
        Are we more accurate than the passed in other position and fit into
        the other's position range?
        """
        if not self.found():
            return False
        if not other.found():
            return True
        if (self.source != other.source) and (self.source < other.source):
            return True
        return (self.agrees_with(other) and self.accuracy < other.accuracy)


class Country(Result):
    """The country returned by a country query."""

    _required = ('country_code', 'country_name')  #:

    @property
    def data_accuracy(self):
        if not self.found():
            return DataAccuracy.none
        return DataAccuracy.low

    def agrees_with(self, other):
        return self.country_code == other.country_code

    def accurate_enough(self, query):
        return self.found()

    def more_accurate(self, other):
        if not self.found():
            return False
        if not other.found():
            return True
        if self.source < other.source:
            return True
        return False
