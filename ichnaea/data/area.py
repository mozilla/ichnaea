import numpy

from ichnaea.data.base import DataTask
from ichnaea.geocalc import centroid, circle_radius
from ichnaea.models import (
    Cell,
    CellArea,
    OCIDCell,
    OCIDCellArea,
)
from ichnaea import util


class CellAreaUpdater(DataTask):

    cell_model = Cell
    area_model = CellArea

    def __init__(self, task, session):
        DataTask.__init__(self, task, session)
        self.data_queue = self.task.app.data_queues['update_cellarea']
        self.utcnow = util.utcnow()

    def scan(self, update_task, batch=100):
        redis_areas = self.data_queue.dequeue(batch=batch)
        area_keys = list(set(redis_areas))
        batch_size = 10
        for i in range(0, len(area_keys), batch_size):
            area_batch = area_keys[i:i + batch_size]
            update_task.delay(area_batch)
        return len(area_keys)

    def _extreme_value(self, func, column, cells):
        values = [getattr(cell, column, None) for cell in cells]
        values = [value for value in values if value is not None]
        return func(values)

    def update(self, area_keys):
        if isinstance(area_keys, (list, tuple)):
            for area_key in area_keys:
                self.update_area(area_key)
        else:  # pragma: no cover
            # BBB the task used to be called with a single area key
            self.update_area(area_keys)

    def update_area(self, area_key):
        # Select all cells in this area and derive a bounding box for them
        cell_query = (self.cell_model.querykey(self.session, area_key)
                                     .filter(self.cell_model.lat.isnot(None))
                                     .filter(self.cell_model.lon.isnot(None)))
        cells = cell_query.all()

        area_query = self.area_model.querykey(self.session, area_key)
        if len(cells) == 0:
            # If there are no more underlying cells, delete the area entry
            area_query.delete()
        else:
            # Otherwise update the area entry based on all the cells
            area = area_query.first()

            min_lat = self._extreme_value(min, 'min_lat', cells)
            min_lon = self._extreme_value(min, 'min_lon', cells)
            max_lat = self._extreme_value(max, 'max_lat', cells)
            max_lon = self._extreme_value(max, 'max_lon', cells)

            bbox_points = [(min_lat, min_lon),
                           (min_lat, max_lon),
                           (max_lat, min_lon),
                           (max_lat, max_lon)]

            ctr_lat, ctr_lon = centroid(
                numpy.array([(c.lat, c.lon) for c in cells],
                            dtype=numpy.float64))
            radius = circle_radius(ctr_lat, ctr_lon, bbox_points)

            # Now create or update the area
            num_cells = len(cells)
            avg_cell_range = int(sum(
                [cell.range for cell in cells]) / float(num_cells))
            if area is None:
                stmt = self.area_model.__table__.insert(
                    mysql_on_duplicate='num_cells = num_cells'  # no-op
                ).values(
                    created=self.utcnow,
                    modified=self.utcnow,
                    lat=ctr_lat,
                    lon=ctr_lon,
                    range=radius,
                    avg_cell_range=avg_cell_range,
                    num_cells=num_cells,
                    **area_key.__dict__
                )
                self.session.execute(stmt)
            else:
                area.modified = self.utcnow
                area.lat = ctr_lat
                area.lon = ctr_lon
                area.range = radius
                area.avg_cell_range = avg_cell_range
                area.num_cells = num_cells


class OCIDCellAreaUpdater(CellAreaUpdater):

    cell_model = OCIDCell
    area_model = OCIDCellArea
