"""Implementation of a search source based on our internal data."""

from ichnaea.api.locate.cell import (
    CellPositionMixin,
    CellRegionMixin,
)
from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.result import (
    RegionResultList,
)
from ichnaea.api.locate.source import (
    PositionSource,
    RegionSource,
)
from ichnaea.api.locate.wifi import (
    WifiPositionMixin,
    WifiRegionMixin,
)


class InternalRegionSource(CellRegionMixin,
                           WifiRegionMixin, RegionSource):
    """A region source based on our own crowd-sourced internal data."""

    fallback_field = None  #:
    source = DataSource.internal  #:

    def should_search(self, query, results):
        if not RegionSource.should_search(
                self, query, results):  # pragma: no cover
            return False
        if not (self.should_search_cell(query, results) or
                self.should_search_wifi(query, results)):
            return False
        return True

    def search(self, query):
        results = RegionResultList()
        for should, search in (
            # start with cell search, we don't need precise results
                (self.should_search_cell, self.search_cell),
                (self.should_search_wifi, self.search_wifi)):

            if should(query, results):
                results.add(search(query))
                if results.satisfies(query):
                    # If we have a good enough result, stop.
                    break

        if len(results):
            query.emit_source_stats(
                self.source, results.best(query.expected_accuracy))
        else:
            results.add(self.result_type())
        return results


class InternalPositionSource(CellPositionMixin,
                             WifiPositionMixin, PositionSource):
    """A position source based on our own crowd-sourced internal data."""

    fallback_field = None  #:
    source = DataSource.internal  #:

    def should_search(self, query, results):
        if not PositionSource.should_search(
                self, query, results):  # pragma: no cover
            return False
        if not (self.should_search_cell(query, results) or
                self.should_search_wifi(query, results)):
            return False
        return True

    def search(self, query):
        results = self.result_type().as_list()
        for should, search in (
            # start with wifi search, we want precise results
                (self.should_search_wifi, self.search_wifi),
                (self.should_search_cell, self.search_cell)):

            if should(query, results):
                results.add(search(query))
                if results.satisfies(query):
                    # If we have a good enough result, stop.
                    break

        query.emit_source_stats(
            self.source, results.best(query.expected_accuracy))
        return results
