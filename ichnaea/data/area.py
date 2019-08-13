from collections import defaultdict

import numpy
from sqlalchemy import delete, select

from geocalc import circle_radius
from ichnaea.geocode import GEOCODER
from ichnaea.models import (
    decode_cellarea,
    CellArea,
    CellShard,
)
from ichnaea import util


class CellAreaUpdater(object):

    area_table = CellArea.__table__
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
        load_fields = ('cellid', 'lat', 'lon', 'radius', 'region', 'last_seen',
                       'max_lat', 'max_lon', 'min_lat', 'min_lon')

        shard = self.cell_model.shard_model(radio)
        fields = [getattr(shard.__table__.c, f) for f in load_fields]

        cells = session.execute(
            select(fields)
            .where(shard.__table__.c.radio == radio)
            .where(shard.__table__.c.mcc == mcc)
            .where(shard.__table__.c.mnc == mnc)
            .where(shard.__table__.c.lac == lac)
            .where(shard.__table__.c.lat.isnot(None))
            .where(shard.__table__.c.lon.isnot(None))
        ).fetchall()

        if len(cells) == 0:
            # If there are no more underlying cells, delete the area entry
            session.execute(
                delete(self.area_table)
                .where(self.area_table.c.areaid == areaid)
            )
            return

        # Otherwise update the area entry based on all the cells
        area = session.execute(
            select([self.area_table.c.areaid,
                    self.area_table.c.modified,
                    self.area_table.c.lat,
                    self.area_table.c.lon,
                    self.area_table.c.radius,
                    self.area_table.c.region,
                    self.area_table.c.avg_cell_radius,
                    self.area_table.c.num_cells,
                    self.area_table.c.last_seen,
                    ])
            .where(self.area_table.c.areaid == areaid)
        ).fetchone()

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
            session.execute(
                self.area_table.insert(
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
            )
        else:
            session.execute(
                self.area_table.update()
                .where(self.area_table.c.areaid == areaid)
                .values(
                    modified=self.utcnow,
                    lat=ctr_lat,
                    lon=ctr_lon,
                    radius=radius,
                    region=region,
                    avg_cell_radius=avg_cell_radius,
                    num_cells=num_cells,
                    last_seen=last_seen,
                )
            )
