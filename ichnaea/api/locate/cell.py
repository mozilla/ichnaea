"""Implementation of a search provider using a cell database."""

from collections import defaultdict
import operator

import mobile_codes
from sqlalchemy.orm import load_only

from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.provider import (
    Network,
    Provider,
)
from ichnaea.api.locate.result import (
    Country,
    Position,
)
from ichnaea.constants import (
    CELL_MIN_ACCURACY,
    LAC_MIN_ACCURACY,
)
from ichnaea.models import (
    Cell,
    CellArea,
    OCIDCell,
    OCIDCellArea,
)


class BaseCellProvider(Provider):
    """
    An BaseCellProvider provides an interface and
    partial implementation of a search using a
    model which has a Cell-like set of fields.

    .. attribute:: model

        A model which has a Cell interface to be used
        in the search.
    """

    model = None
    log_name = 'cell'
    result_type = Position
    query_field = 'cell'

    def _clean_cell_keys(self, query):
        """Pre-process cell query."""
        return [cell.hashkey() for cell in getattr(query, self.query_field)]

    def _query_database(self, query, cell_keys):
        """Query the cell model."""
        try:
            load_fields = ('lat', 'lon', 'range')
            cell_iter = self.model.iterkeys(
                query.session,
                cell_keys,
                extra=lambda query: query.options(load_only(*load_fields))
                                         .filter(self.model.lat.isnot(None))
                                         .filter(self.model.lon.isnot(None)))

            return self._filter_cells(list(cell_iter))
        except Exception:
            self.raven_client.captureException()
            return []

    def _filter_cells(self, found_cells):
        # Group all found_cells by cell area
        areas = defaultdict(list)
        for cell in found_cells:
            areas[CellArea.to_hashkey(cell)].append(cell)

        def sort_lac(v):
            # use the area with the most values,
            # or the one with the smallest range
            return (len(v), -min([e.range for e in v]))

        # If we get data from multiple cell areas, use the one
        # with the most data points in it. That way an area with a cell
        # hit will have two entries and win over an area with only the
        # area entry.
        areas = sorted(areas.values(), key=sort_lac, reverse=True)
        if not areas:
            return []

        return [Network(
            key=None,
            lat=cell.lat,
            lon=cell.lon,
            range=cell.range,
        ) for cell in areas[0]]

    def _prepare(self, queried_cells):
        """
        Combine the queried_cells into an estimated result.

        :rtype: :class:`~ichnaea.api.locate.result.Result`
        """
        length = len(queried_cells)
        avg_lat = sum([c.lat for c in queried_cells]) / length
        avg_lon = sum([c.lon for c in queried_cells]) / length
        accuracy = self._estimate_accuracy(
            avg_lat, avg_lon, queried_cells, CELL_MIN_ACCURACY)
        return self.result_type(lat=avg_lat, lon=avg_lon, accuracy=accuracy)

    def search(self, query):
        result = self.result_type(query_data=False)
        cell_keys = self._clean_cell_keys(query)
        if cell_keys:
            result.query_data = True
            queried_cells = self._query_database(query, cell_keys)
            if queried_cells:
                result = self._prepare(queried_cells)
        return result


class CellPositionProvider(BaseCellProvider):
    """
    A CellPositionProvider implements a cell search using the Cell model.
    """

    model = Cell


class OCIDCellPositionProvider(BaseCellProvider):
    """
    A OCIDCellPositionProvider implements a cell search using
    the OCID Cell model.
    """

    model = OCIDCell
    source = DataSource.OCID


class CellAreaPositionProvider(BaseCellProvider):
    """
    A CellAreaPositionProvider implements a cell search
    using the CellArea model.
    """

    model = CellArea
    log_name = 'cell_lac'
    fallback_field = 'lacf'
    query_field = 'cell_area'

    def _prepare(self, queried_cells):
        # take the smallest LAC of any the user is inside
        lac = sorted(queried_cells, key=operator.attrgetter('range'))[0]
        accuracy = float(max(LAC_MIN_ACCURACY, lac.range))
        return self.result_type(lat=lac.lat, lon=lac.lon, accuracy=accuracy)


class OCIDCellAreaPositionProvider(CellAreaPositionProvider):
    """
    A OCIDCellAreaPositionProvider implements a cell search
    using the OCIDCellArea model.
    """

    model = OCIDCellArea
    source = DataSource.OCID


class CellCountryProvider(BaseCellProvider):
    """
    A CellCountryProvider implements a cell country search without
    using any DB models.
    """

    result_type = Country
    model = CellArea

    def _query_database(self, query, cell_keys):
        countries = []
        for key in cell_keys:
            countries.extend(mobile_codes.mcc(str(key.mcc)))
        if len(set([c.alpha2 for c in countries])) != 1:
            # refuse to guess country if there are multiple choices
            return []
        return countries[0]

    def _prepare(self, obj):
        return self.result_type(country_code=obj.alpha2,
                                country_name=obj.name)
