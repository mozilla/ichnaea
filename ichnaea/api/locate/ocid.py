"""Search implementation using the :term:`OCID` cell database."""

from ichnaea.api.locate.cell import CellPositionSource
from ichnaea.api.locate.constants import DataSource
from ichnaea.models import (
    OCIDCell,
    OCIDCellArea,
)


class OCIDPositionSource(CellPositionSource):
    """Implements a search using the :term:`OCID` cell data."""

    cell_model = OCIDCell
    area_model = OCIDCellArea
    fallback_field = None  #:
    source = DataSource.ocid  #:
