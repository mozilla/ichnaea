"""Search implementation using a cell database."""

from collections import defaultdict
import operator

import numpy
from sqlalchemy.orm import load_only
from sqlalchemy.sql import or_

from ichnaea.api.locate.constants import (
    DataSource,
    CELL_MIN_ACCURACY,
    CELL_MAX_ACCURACY,
    CELLAREA_MIN_ACCURACY,
    CELLAREA_MAX_ACCURACY,
)
from ichnaea.api.locate.result import (
    Position,
    Region,
    ResultList,
)
from ichnaea.api.locate.source import PositionSource
from ichnaea.constants import (
    PERMANENT_BLOCKLIST_THRESHOLD,
    TEMPORARY_BLOCKLIST_DURATION,
)
from ichnaea.geocalc import aggregate_position
from ichnaea.geocode import GEOCODER
from ichnaea.models import (
    CellArea,
    CellAreaOCID,
    CellOCID,
    CellShard,
)
from ichnaea import util


def pick_best_cells(cells):
    """
    Group cells by area, pick the best cell area. Either
    the one with the most values or the smallest radius.
    """
    areas = defaultdict(list)
    for cell in cells:
        areas[cell.areaid].append(cell)

    def sort_areas(areas):
        return (len(areas), -min([cell.radius for cell in areas]))

    areas = sorted(areas.values(), key=sort_areas, reverse=True)
    return areas[0]


def pick_best_area(areas):
    """Sort areas by size, pick the smallest one."""
    areas = sorted(areas, key=operator.attrgetter('radius'))
    return areas[0]


def aggregate_cell_position(cells, result_type, now):
    """
    Given a list of cells from a single cell cluster,
    return the aggregate position of the user inside the cluster.
    """
    circles = numpy.array(
        [(cell.lat, cell.lon, cell.radius) for cell in cells],
        dtype=numpy.double)
    lat, lon, accuracy = aggregate_position(circles, CELL_MIN_ACCURACY)
    accuracy = min(accuracy, CELL_MAX_ACCURACY)
    score = sum([cell.score(now) for cell in cells])

    return result_type(
        lat=lat, lon=lon, accuracy=accuracy, score=score)


def aggregate_area_position(area, result_type, now):
    """
    Given a single area, return the position of the user inside it.
    """
    accuracy = max(float(area.radius), CELLAREA_MIN_ACCURACY)
    accuracy = min(accuracy, CELLAREA_MAX_ACCURACY)
    score = area.score(now)

    return result_type(
        lat=area.lat, lon=area.lon, accuracy=accuracy, score=score,
        fallback='lacf')


def query_cell_table(session, model, cellids, temp_blocked,
                     load_fields, raven_client):
    try:
        return (
            session.query(model)
                   .filter(model.cellid.in_(cellids))
                   .filter(model.lat.isnot(None))
                   .filter(model.lon.isnot(None))
                   .filter(or_(
                       model.block_count.is_(None),
                       model.block_count <
                           PERMANENT_BLOCKLIST_THRESHOLD))
                   .filter(or_(
                       model.block_last.is_(None),
                       model.block_last < temp_blocked))
                   .options(load_only(*load_fields))
        ).all()
    except Exception:
        raven_client.captureException()
    return []


def query_cells(query, lookups, model, raven_client):
    # Given a location query and a list of lookup instances, query the
    # database and return a list of model objects.
    cellids = [lookup.cellid for lookup in lookups]
    if not cellids:  # pragma: no cover
        return []

    # load all fields used in score calculation and those we
    # need for the position
    load_fields = ('lat', 'lon', 'radius',
                   'created', 'modified', 'samples')

    today = util.utcnow().date()
    temp_blocked = today - TEMPORARY_BLOCKLIST_DURATION

    if model == CellOCID:
        # non sharded OCID table
        return query_cell_table(query.session, model, cellids,
                                temp_blocked, load_fields, raven_client)

    result = []
    shards = defaultdict(list)
    for lookup in lookups:
        shards[CellShard.shard_model(lookup.radio)].append(lookup.cellid)

    for shard, shard_cellids in shards.items():
        result.extend(
            query_cell_table(query.session, shard, shard_cellids,
                             temp_blocked, load_fields, raven_client))

    return result


def query_areas(query, lookups, model, raven_client):
    areaids = [lookup.areaid for lookup in lookups]
    if not areaids:  # pragma: no cover
        return []

    # load all fields used in score calculation and those we
    # need for the position
    load_fields = ('lat', 'lon', 'radius',
                   'created', 'modified', 'num_cells')
    try:
        areas = (query.session.query(model)
                              .filter(model.areaid.in_(areaids))
                              .filter(model.lat.isnot(None))
                              .filter(model.lon.isnot(None))
                              .options(load_only(*load_fields))).all()

        return areas
    except Exception:
        raven_client.captureException()
    return []


class CellPositionMixin(object):
    """
    A CellPositionMixin implements a position search using the cell models.
    """

    cell_model = CellShard
    area_model = CellArea
    result_type = Position

    def should_search_cell(self, query, results):
        if not (query.cell or query.cell_area):
            return False
        return True

    def search_cell(self, query):
        result = self.result_type()
        now = util.utcnow()

        if query.cell:
            cells = query_cells(
                query, query.cell, self.cell_model, self.raven_client)
            if cells:
                best_cells = pick_best_cells(cells)
                result = aggregate_cell_position(
                    best_cells, self.result_type, now)

            if not result.empty():
                return result

        if query.cell_area:
            areas = query_areas(
                query, query.cell_area, self.area_model, self.raven_client)
            if areas:
                best_area = pick_best_area(areas)
                result = aggregate_area_position(
                    best_area, self.result_type, now)

        return result


class CellRegionMixin(object):
    """
    A CellRegionMixin implements a region search using the cell models.
    """

    result_type = Region

    def should_search_cell(self, query, results):
        if not (query.cell or query.cell_area):
            return False
        return True

    def search_mcc(self, query):
        results = ResultList()

        codes = []
        for cell in list(query.cell) + list(query.cell_area):
            codes.append(cell.mcc)

        regions = []
        for code in codes:
            mcc_regions = GEOCODER.regions_for_mcc(code, metadata=True)
            # divide score by number of possible regions for the mcc
            score = 1.0 / (len(mcc_regions) or 1.0)
            for mcc_region in mcc_regions:
                regions.append((mcc_region, score))

        # group by region code
        grouped_regions = {}
        for region, score in regions:
            code = region.code
            if code not in grouped_regions:
                grouped_regions[code] = [region, score]
            else:
                # sum up scores of multiple matches
                grouped_regions[code][1] += score

        for region, score in grouped_regions.values():
            results.add(self.result_type(
                region_code=region.code,
                region_name=region.name,
                accuracy=region.radius,
                score=score))
        return results


class CellPositionSource(CellPositionMixin, PositionSource):
    """
    Implements a search using our cell data.

    This source is only used in tests and as a base for the
    OCIDPositionSource.
    """

    fallback_field = None  #:
    source = DataSource.internal

    def should_search(self, query, results):
        return self.should_search_cell(query, results)

    def search(self, query):
        result = self.search_cell(query)
        query.emit_source_stats(self.source, result)
        return result


class OCIDPositionSource(CellPositionSource):
    """Implements a search using the :term:`OCID` cell data."""

    cell_model = CellOCID
    area_model = CellAreaOCID
    fallback_field = None  #:
    source = DataSource.ocid  #:
