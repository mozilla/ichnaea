"""Implementation of a search source based on our internal data."""

from ichnaea.api.locate.cell import CellPositionMixin
from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.result import ResultList
from ichnaea.api.locate.source import (
    PositionSource,
    RegionSource,
)
from ichnaea.api.locate.wifi import WifiPositionMixin
from ichnaea.geocode import GEOCODER


class InternalRegionSource(RegionSource):
    """A region source based on our own crowd-sourced internal data."""

    source = DataSource.internal  #:

    def search(self, query):
        results = ResultList()

        codes = set()
        for cell in list(query.cell) + list(query.cell_area):
            codes.add(cell.mcc)

        regions = []
        for code in codes:
            regions.extend(GEOCODER.regions_for_mcc(code, metadata=True))

        for region in regions:
            region_code = region.code
            results.add(self.result_type(
                region_code=region_code,
                region_name=region.name,
                accuracy=region.radius))

        if len(results):
            query.emit_source_stats(self.source, results[0])
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
        results = ResultList(self.result_type())
        for should, search in (
                (self.should_search_wifi, self.search_wifi),
                (self.should_search_cell, self.search_cell)):

            if should(query, results):
                results.add(search(query))
                if results.satisfies(query):
                    # If we have a good enough result, stop.
                    break

        query.emit_source_stats(self.source, results.best())
        return results
