from ichnaea.data.base import DataTask
from ichnaea.geocalc import centroid, range_to_points
from ichnaea.models import (
    Cell,
    CellArea,
    OCIDCell,
    OCIDCellArea,
)
from ichnaea import util


class CellAreaUpdater(DataTask):

    cell_model = Cell
    cell_area_model = CellArea

    def __init__(self, task, session):
        DataTask.__init__(self, task, session)
        self.data_queue = self.task.app.data_queues['update_cellarea']
        self.utcnow = util.utcnow()

    def scan(self, update_task, batch=100):
        redis_areas = self.data_queue.dequeue(batch=batch)
        area_keys = set(redis_areas)
        for area_key in area_keys:
            update_task.delay(area_key)
        return len(area_keys)

    def update(self, area_key):
        # Select all cells in this area and derive a bounding box for them
        cell_query = (self.cell_model.querykey(self.session, area_key)
                                     .filter(self.cell_model.lat.isnot(None))
                                     .filter(self.cell_model.lon.isnot(None)))
        cells = cell_query.all()

        area_query = self.cell_area_model.querykey(self.session, area_key)
        if len(cells) == 0:
            # If there are no more underlying cells, delete the area entry
            area_query.delete()
        else:
            # Otherwise update the area entry based on all the cells
            area = area_query.first()

            points = [(c.lat, c.lon) for c in cells]
            min_lat = min([c.min_lat for c in cells])
            min_lon = min([c.min_lon for c in cells])
            max_lat = max([c.max_lat for c in cells])
            max_lon = max([c.max_lon for c in cells])

            bbox_points = [(min_lat, min_lon),
                           (min_lat, max_lon),
                           (max_lat, min_lon),
                           (max_lat, max_lon)]

            ctr = centroid(points)
            rng = range_to_points(ctr, bbox_points)

            # Switch units back to meters
            ctr_lat = ctr[0]
            ctr_lon = ctr[1]
            rng = int(round(rng * 1000.0))

            # Now create or update the area
            num_cells = len(cells)
            avg_cell_range = int(sum(
                [cell.range for cell in cells]) / float(num_cells))
            if area is None:
                area = self.cell_area_model(
                    created=self.utcnow,
                    modified=self.utcnow,
                    lat=ctr_lat,
                    lon=ctr_lon,
                    range=rng,
                    avg_cell_range=avg_cell_range,
                    num_cells=num_cells,
                    **area_key.__dict__)
                self.session.add(area)
            else:
                area.modified = self.utcnow
                area.lat = ctr_lat
                area.lon = ctr_lon
                area.range = rng
                area.avg_cell_range = avg_cell_range
                area.num_cells = num_cells


class OCIDCellAreaUpdater(CellAreaUpdater):

    cell_model = OCIDCell
    cell_area_model = OCIDCellArea
