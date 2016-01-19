"""Implementation of a search source based on our internal data."""

from ichnaea.api.locate.cell import (
    CellPositionMixin,
    CellRegionMixin,
)
from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.source import (
    PositionSource,
    RegionSource,
)
from ichnaea.api.locate.wifi import (
    WifiPositionMixin,
    WifiRegionMixin,
)


class BaseInternalSource(object):
    """A source based on our own crowd-sourced internal data."""

    fallback_field = None  #:
    source = DataSource.internal  #:

    def should_search(self, query, results):
        if not super(BaseInternalSource, self).should_search(
                query, results):  # pragma: no cover
            return False
        if not (self.should_search_cell(query, results) or
                self.should_search_wifi(query, results)):
            return False
        return True

    def search(self, query):
        results = self.result_type().new_list()

        for should, search in (
                (self.should_search_wifi, self.search_wifi),
                (self.should_search_cell, self.search_cell)):

            if should(query, results):
                results.add(search(query))

        query.emit_source_stats(self.source, results)
        return results


class InternalPositionSource(BaseInternalSource,
                             CellPositionMixin,
                             WifiPositionMixin,
                             PositionSource):
    """A position source based on our own crowd-sourced internal data."""


class InternalRegionSource(BaseInternalSource,
                           CellRegionMixin,
                           WifiRegionMixin,
                           RegionSource):
    """A region source based on our own crowd-sourced internal data."""
