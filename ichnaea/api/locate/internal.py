"""Implementation of a search source based on our internal data."""

from ichnaea.api.locate.cell import CellPositionMixin
from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.result import ResultList
from ichnaea.api.locate.source import (
    CountrySource,
    PositionSource,
)
from ichnaea.api.locate.wifi import WifiPositionMixin
from ichnaea.geoip import geoip_accuracy
from ichnaea.region import GEOCODER


class InternalCountrySource(CountrySource):
    """A country source based on our own crowd-sourced internal data."""

    source = DataSource.internal  #:

    def search(self, query):
        results = ResultList()

        codes = set()
        for cell in list(query.cell) + list(query.cell_area):
            codes.add(cell.mcc)

        countries = []
        for code in codes:
            countries.extend(GEOCODER.regions_for_mcc(code))

        for country in countries:
            country_code = country.alpha2
            results.add(self.result_type(
                country_code=country_code,
                country_name=country.name,
                accuracy=geoip_accuracy(country_code)))

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
