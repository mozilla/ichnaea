"""Search implementation using the OCID cell database."""

from ichnaea.api.locate.cell import CellPositionMixin
from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.source import PositionSource
from ichnaea.models import (
    OCIDCell,
    OCIDCellArea,
)


class OCIDPositionSource(CellPositionMixin, PositionSource):
    """Implements a search using the OCID cell data."""

    cell_model = OCIDCell
    cell_area_model = OCIDCellArea
    fallback_field = None  #:
    source = DataSource.ocid  #:

    def search(self, query):
        result = self.result_type()
        if not (query.cell or query.cell_area):
            return result

        for func in (self.search_cell, self.search_cell_area):
            new_result = func(query)
            if new_result.more_accurate(result):
                result = new_result

            if result.accurate_enough():  # pragma: no cover
                break

        query.emit_source_stats(self.source, result)
        return result
