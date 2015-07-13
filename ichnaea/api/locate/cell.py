from collections import defaultdict
import operator

import mobile_codes
from sqlalchemy.orm import load_only

from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.location import (
    Country,
    Position,
)
from ichnaea.api.locate.provider import (
    Network,
    Provider,
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
        in the location search.
    """

    model = None
    log_name = 'cell'
    location_type = Position
    query_field = 'cell'

    def _clean_cell_keys(self, query):
        """Pre-process cell query."""
        cell_keys = []
        for cell in getattr(query, self.query_field):
            cell_key = self.model.to_hashkey(cell)
            cell_keys.append(cell_key)

        return cell_keys

    def _query_database(self, cell_keys):
        """Query the cell model."""
        try:
            load_fields = ('lat', 'lon', 'range')
            cell_iter = self.model.iterkeys(
                self.session_db,
                cell_keys,
                extra=lambda query: query.options(load_only(*load_fields))
                                         .filter(self.model.lat.isnot(None))
                                         .filter(self.model.lon.isnot(None)))

            return self._filter_cells(list(cell_iter))
        except Exception:
            self.raven_client.captureException()
            return []

    def _filter_cells(self, found_cells):
        # Group all found_cells by location area
        lacs = defaultdict(list)
        for cell in found_cells:
            cellarea_key = (cell.radio, cell.mcc, cell.mnc, cell.lac)
            lacs[cellarea_key].append(cell)

        def sort_lac(v):
            # use the lac with the most values,
            # or the one with the smallest range
            return (len(v), -min([e.range for e in v]))

        # If we get data from multiple location areas, use the one
        # with the most data points in it. That way a lac with a cell
        # hit will have two entries and win over a lac with only the
        # lac entry.
        lac = sorted(lacs.values(), key=sort_lac, reverse=True)
        if not lac:
            return []

        return [Network(
            key=None,
            lat=cell.lat,
            lon=cell.lon,
            range=cell.range,
        ) for cell in lac[0]]

    def _prepare(self, queried_cells):
        """
        Combine the queried_cells into an estimated location.

        :rtype: :class:`~ichnaea.api.locate.location.Location`
        """
        length = len(queried_cells)
        avg_lat = sum([c.lat for c in queried_cells]) / length
        avg_lon = sum([c.lon for c in queried_cells]) / length
        accuracy = self._estimate_accuracy(
            avg_lat, avg_lon, queried_cells, CELL_MIN_ACCURACY)
        return self.location_type(lat=avg_lat, lon=avg_lon, accuracy=accuracy)

    def locate(self, query):
        location = self.location_type(query_data=False)
        cell_keys = self._clean_cell_keys(query)
        if cell_keys:
            location.query_data = True
            queried_cells = self._query_database(cell_keys)
            if queried_cells:
                location = self._prepare(queried_cells)
        return location


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
        return self.location_type(lat=lac.lat, lon=lac.lon, accuracy=accuracy)


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

    location_type = Country
    model = CellArea

    def _query_database(self, cell_keys):
        countries = []
        for key in cell_keys:
            countries.extend(mobile_codes.mcc(str(key.mcc)))
        if len(set([c.alpha2 for c in countries])) != 1:
            # refuse to guess country if there are multiple choices
            return []
        return countries[0]

    def _prepare(self, obj):
        return self.location_type(country_code=obj.alpha2,
                                  country_name=obj.name)
