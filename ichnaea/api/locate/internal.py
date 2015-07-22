"""Implementation of a search source based on our internal data."""

import mobile_codes

from ichnaea.api.locate.cell import CellPositionMixin
from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.source import (
    CountrySource,
    PositionSource,
)
from ichnaea.api.locate.wifi import WifiPositionMixin


class InternalCountrySource(CountrySource):
    """A country source based on our own crowd-sourced internal data."""

    source = DataSource.internal  #:

    def search(self, query):
        result = self.result_type()

        codes = set()
        for cell in list(query.cell) + list(query.cell_area):
            codes.add(cell.mcc)

        countries = []
        for code in codes:
            countries.extend(mobile_codes.mcc(str(code)))

        if countries:
            if len(countries) == 1:
                # refuse to guess country if there are multiple choices
                result = self.result_type(
                    country_code=countries[0].alpha2,
                    country_name=countries[0].name)

            query.emit_source_stats(self.source, result)

        return result


class InternalPositionSource(CellPositionMixin,
                             WifiPositionMixin, PositionSource):
    """A position source based on our own crowd-sourced internal data."""

    source = DataSource.internal  #:

    def search(self, query):
        result = self.result_type()
        if not (query.wifi or query.cell or query.cell_area):
            return result

        for func in (self.search_cell,
                     self.search_cell_area,
                     self.search_wifi):

            new_result = func(query)
            if new_result.more_accurate(result):
                result = new_result

            if result.accurate_enough():  # pragma: no cover
                break

        query.emit_source_stats(self.source, result)
        return result
