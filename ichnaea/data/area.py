from collections import defaultdict

import numpy
from sqlalchemy.orm import load_only

from ichnaea.geocalc import (
    circle_radius,
)
from ichnaea.geocode import GEOCODER
from ichnaea.models import (
    decode_cellarea,
    CellArea,
    CellAreaOCID,
    CellOCID,
    CellShard,
)
from ichnaea import util


class CellAreaUpdater(object):

    area_model = CellArea
    cell_model = CellShard
    queue_name = 'update_cellarea'

    def __init__(self, task):
        self.task = task
        self.queue = self.task.app.data_queues[self.queue_name]
        self.utcnow = util.utcnow()

    def __call__(self):
        areaids = self.queue.dequeue()

        with self.task.db_session() as session:
            for areaid in set(areaids):
                self.update_area(session, areaid)

        if self.queue.ready():  # pragma: no cover
            self.task.apply_countdown()

    def region(self, ctr_lat, ctr_lon, mcc, cells):
        region = None
        regions = [cell.region for cell in cells]
        unique_regions = set(regions)
        if len(unique_regions) == 1:
            region = regions[0]
        else:
            # Choose the area region based on the majority of cells
            # inside each region.
            grouped_regions = defaultdict(int)
            for reg in regions:
                grouped_regions[reg] += 1
            max_count = max(grouped_regions.values())
            max_regions = sorted([k for k, v in grouped_regions.items()
                                  if v == max_count])
            # If we get a tie here, randomly choose the first.
            region = max_regions[0]
            if len(max_regions) > 1:
                # Try to break the tie based on the center of the area,
                # but keep the randomly chosen region if this fails.
                area_region = GEOCODER.region_for_cell(
                    ctr_lat, ctr_lon, mcc)
                if area_region is not None:
                    region = area_region

        return region

    def update_area(self, session, areaid):
        # Select all cells in this area and derive a bounding box for them
        radio, mcc, mnc, lac = decode_cellarea(areaid)
        load_fields = ('lat', 'lon', 'radius', 'region', 'last_seen',
                       'max_lat', 'max_lon', 'min_lat', 'min_lon')

        shard = self.cell_model.shard_model(radio)
        cells = (session.query(shard)
                        .filter((shard.radio == radio),
                                (shard.mcc == mcc),
                                (shard.mnc == mnc),
                                (shard.lac == lac),
                                shard.lat.isnot(None),
                                shard.lon.isnot(None))
                        .options(load_only(*load_fields))).all()

        area_query = (session.query(self.area_model)
                             .filter(self.area_model.areaid == areaid))

        if len(cells) == 0:
            # If there are no more underlying cells, delete the area entry
            area_query.delete()
        else:
            # Otherwise update the area entry based on all the cells
            area = area_query.first()

            cell_extremes = numpy.array([
                (numpy.nan if cell.max_lat is None else cell.max_lat,
                 numpy.nan if cell.max_lon is None else cell.max_lon)
                for cell in cells] + [
                (numpy.nan if cell.min_lat is None else cell.min_lat,
                 numpy.nan if cell.min_lon is None else cell.min_lon)
                for cell in cells
            ], dtype=numpy.double)

            max_lat, max_lon = numpy.nanmax(cell_extremes, axis=0)
            min_lat, min_lon = numpy.nanmin(cell_extremes, axis=0)

            ctr_lat, ctr_lon = numpy.array(
                [(c.lat, c.lon) for c in cells],
                dtype=numpy.double).mean(axis=0)
            ctr_lat = float(ctr_lat)
            ctr_lon = float(ctr_lon)

            radius = circle_radius(
                ctr_lat, ctr_lon, max_lat, max_lon, min_lat, min_lon)

            cell_radii = numpy.array([
                (numpy.nan if cell.radius is None else cell.radius)
                for cell in cells
            ], dtype=numpy.int32)
            avg_cell_radius = int(round(numpy.nanmean(cell_radii)))
            num_cells = len(cells)
            region = self.region(ctr_lat, ctr_lon, mcc, cells)

            last_seen = None
            cell_last_seen = set([cell.last_seen for cell in cells
                                  if cell.last_seen is not None])
            if cell_last_seen:
                last_seen = max(cell_last_seen)

            if area is None:
                stmt = self.area_model.__table__.insert(
                    mysql_on_duplicate='num_cells = num_cells'  # no-op
                ).values(
                    areaid=areaid,
                    radio=radio,
                    mcc=mcc,
                    mnc=mnc,
                    lac=lac,
                    created=self.utcnow,
                    modified=self.utcnow,
                    lat=ctr_lat,
                    lon=ctr_lon,
                    radius=radius,
                    region=region,
                    avg_cell_radius=avg_cell_radius,
                    num_cells=num_cells,
                    last_seen=last_seen,
                )
                session.execute(stmt)
            else:
                area.modified = self.utcnow
                area.lat = ctr_lat
                area.lon = ctr_lon
                area.radius = radius
                area.region = region
                area.avg_cell_radius = avg_cell_radius
                area.num_cells = num_cells
                area.last_seen = last_seen


class CellAreaOCIDUpdater(CellAreaUpdater):

    area_model = CellAreaOCID
    cell_model = CellOCID
    queue_name = 'update_cellarea_ocid'
