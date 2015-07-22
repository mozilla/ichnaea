"""Search implementation using a cell database."""

from collections import defaultdict, namedtuple
import operator

from sqlalchemy.orm import load_only

from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.result import Position
from ichnaea.constants import (
    CELL_MIN_ACCURACY,
    LAC_MIN_ACCURACY,
)
from ichnaea.geocalc import estimate_accuracy
from ichnaea.models import (
    Cell,
    CellArea,
)

Network = namedtuple('Network', ['key', 'lat', 'lon', 'range'])


class CellPositionMixin(object):
    """
    A CellPositionMixin implements a position search using the cell models.
    """

    cell_model = Cell
    cell_area_model = CellArea
    result_type = Position
    source = DataSource.internal

    def _clean_cell_keys(self, query, query_field):
        return [cell.hashkey() for cell in getattr(query, query_field)]

    def _query_cell_database(self, query, cell_keys, model):
        try:
            load_fields = ('lat', 'lon', 'range')
            cell_iter = model.iterkeys(
                query.session,
                cell_keys,
                extra=lambda query: query.options(load_only(*load_fields))
                                         .filter(model.lat.isnot(None))
                                         .filter(model.lon.isnot(None)))

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

    def _prepare_cell(self, queried_cells):
        # Combine the queried_cells into an estimated result
        length = len(queried_cells)
        avg_lat = sum([c.lat for c in queried_cells]) / length
        avg_lon = sum([c.lon for c in queried_cells]) / length
        accuracy = estimate_accuracy(
            avg_lat, avg_lon, queried_cells, CELL_MIN_ACCURACY)
        return self.result_type(lat=avg_lat, lon=avg_lon, accuracy=accuracy)

    def _prepare_cell_area(self, queried_cells):
        # take the smallest LAC of any the user is inside
        lac = sorted(queried_cells, key=operator.attrgetter('range'))[0]
        accuracy = float(max(LAC_MIN_ACCURACY, lac.range))
        return self.result_type(
            lat=lac.lat, lon=lac.lon, accuracy=accuracy, fallback='lacf')

    def search_cell(self, query):
        result = self.result_type()
        cell_keys = self._clean_cell_keys(query, 'cell')
        if cell_keys:
            queried_cells = self._query_cell_database(
                query, cell_keys, self.cell_model)
            if queried_cells:
                result = self._prepare_cell(queried_cells)
        return result

    def search_cell_area(self, query):
        result = self.result_type()
        cell_keys = self._clean_cell_keys(query, 'cell_area')
        if cell_keys:
            queried_cells = self._query_cell_database(
                query, cell_keys, self.cell_area_model)
            if queried_cells:
                result = self._prepare_cell_area(queried_cells)
        return result
