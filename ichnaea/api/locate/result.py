"""
Classes representing an abstract query result
or a concrete country or position result.
"""

from ichnaea.api.locate.constants import DataAccuracy
from ichnaea.constants import DEGREE_DECIMAL_PLACES

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

    def empty(self):
        """Does this result include any data?"""
        if not self._required:
            return True
        all_fields = []
        for field in self._required:
            all_fields.append(getattr(self, field, None))
        return None in all_fields

    def satisfies(self, query):
        """Does this result match the expected query accuracy?"""
        return False


class ResultList(object):
    """A collection of query results."""

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
            if result.satisfies(query):
                return True
        return False

    def best(self):
        """Return the best result in the collection."""
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
        if self.empty():
            return DataAccuracy.none
        return DataAccuracy.from_number(self.accuracy)

    def satisfies(self, query):
        if self.data_accuracy <= query.expected_accuracy:
            return True
        return False


class Country(Result):
    """The country returned by a country query."""

    _required = ('country_code', 'country_name')  #:

    @property
    def data_accuracy(self):
        if self.empty():
            return DataAccuracy.none
        return DataAccuracy.low

    def satisfies(self, query):
        return not self.empty()
