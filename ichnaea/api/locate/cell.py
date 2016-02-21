"""Search implementation using a cell database."""

from collections import defaultdict

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
    PositionResultList,
    Region,
    RegionResultList,
)
from ichnaea.api.locate.source import PositionSource
from ichnaea.constants import (
    PERMANENT_BLOCKLIST_THRESHOLD,
    TEMPORARY_BLOCKLIST_DURATION,
)
from ichnaea.geocalc import aggregate_position
from ichnaea.geocode import GEOCODER
from ichnaea.models import (
    encode_cellarea,
    encode_cellid,
    CellArea,
    CellAreaOCID,
    CellOCID,
    CellShard,
)
from ichnaea.models.constants import MIN_CELL_SIGNAL
from ichnaea import util

NETWORK_DTYPE = numpy.dtype([
    ('lat', numpy.double),
    ('lon', numpy.double),
    ('radius', numpy.double),
    ('signal', numpy.int32),
    ('score', numpy.double),
])


def cluster_cells(cells, lookups):
    """
    Cluster cells by area.
    """
    now = util.utcnow()

    # Create a dict of cell ids mapped to their signal strength.
    signals = {}
    for lookup in lookups:
        signals[lookup.cellid] = (lookup.signal or
                                  MIN_CELL_SIGNAL[lookup.radio])

    areas = defaultdict(list)
    for cell in cells:
        areas[cell.areaid].append(cell)

    clusters = []
    for area_cells in areas.values():
        clusters.append(numpy.array(
            [(cell.lat, cell.lon, cell.radius,
              signals[encode_cellid(*cell.cellid)], cell.score(now))
             for cell in area_cells],
            dtype=NETWORK_DTYPE))

    return clusters


def cluster_areas(areas, lookups):
    """
    Cluster areas, treat each area as its own cluster.
    """
    now = util.utcnow()

    # Create a dict of area ids mapped to their signal strength.
    signals = {}
    for lookup in lookups:
        signals[lookup.areaid] = (lookup.signal or
                                  MIN_CELL_SIGNAL[lookup.radio])

    clusters = []
    for area in areas:
        clusters.append(numpy.array(
            [(area.lat, area.lon, area.radius,
              signals[encode_cellarea(*area.areaid)], area.score(now))],
            dtype=NETWORK_DTYPE))

    return clusters


def aggregate_cell_position(cluster, result_type):
    """
    Given a cell cluster, return the aggregate position of the user
    inside the cluster.
    """
    circles = numpy.array(
        [(net[0], net[1], net[2])
         for net in cluster[['lat', 'lon', 'radius']]],
        dtype=numpy.double)

    lat, lon, accuracy = aggregate_position(circles, CELL_MIN_ACCURACY)
    accuracy = min(accuracy, CELL_MAX_ACCURACY)
    score = float(cluster['score'].sum())
    return result_type(lat=lat, lon=lon, accuracy=accuracy, score=score)


def aggregate_area_position(cluster, result_type):
    """
    Given an area cluster, return the aggregate position of the user
    inside the cluster.
    """
    circles = numpy.array(
        [(net[0], net[1], net[2])
         for net in cluster[['lat', 'lon', 'radius']]],
        dtype=numpy.double)

    lat, lon, accuracy = aggregate_position(circles, CELLAREA_MIN_ACCURACY)
    accuracy = min(accuracy, CELLAREA_MAX_ACCURACY)
    score = float(cluster['score'].sum())
    return result_type(lat=lat, lon=lon, accuracy=accuracy, score=score,
                       fallback='lacf')


def query_cell_table(session, model, cellids, temp_blocked,
                     load_fields, raven_client):
    try:
        return (
            session.query(model)
                   .filter(model.cellid.in_(cellids),
                           model.lat.isnot(None),
                           model.lon.isnot(None),
                           or_(model.block_count.is_(None),
                               model.block_count <
                               PERMANENT_BLOCKLIST_THRESHOLD),
                           or_(model.block_last.is_(None),
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
    load_fields = ('lat', 'lon', 'radius', 'region', 'samples',
                   'created', 'modified', 'last_seen', 'block_last')

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
    # need for the position or region
    load_fields = ('lat', 'lon', 'radius', 'region',
                   'created', 'modified', 'num_cells')
    try:
        areas = (query.session.query(model)
                              .filter(model.areaid.in_(areaids),
                                      model.lat.isnot(None),
                                      model.lon.isnot(None))
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
    result_list = PositionResultList
    result_type = Position

    def should_search_cell(self, query, results):
        if not (query.cell or query.cell_area):
            return False
        return True

    def search_cell(self, query):
        results = self.result_list()

        if query.cell:
            cells = query_cells(
                query, query.cell, self.cell_model, self.raven_client)
            if cells:
                for cluster in cluster_cells(cells, query.cell):
                    results.add(aggregate_cell_position(
                        cluster, self.result_type))

            if len(results):
                return results

        if query.cell_area:
            areas = query_areas(
                query, query.cell_area, self.area_model, self.raven_client)
            if areas:
                for cluster in cluster_areas(areas, query.cell_area):
                    results.add(aggregate_area_position(
                        cluster, self.result_type))

        return results


class CellRegionMixin(object):
    """
    A CellRegionMixin implements a region search using the cell models.
    """

    area_model = CellArea
    result_list = RegionResultList
    result_type = Region

    def should_search_cell(self, query, results):
        if not (query.cell or query.cell_area):
            return False
        return True

    def search_cell(self, query):
        results = self.result_list()
        now = util.utcnow()

        ambiguous_cells = []
        regions = []
        for cell in list(query.cell) + list(query.cell_area):
            code = cell.mcc
            mcc_regions = GEOCODER.regions_for_mcc(code, metadata=True)
            # Divide score by number of possible regions for the mcc
            score = 1.0 / (len(mcc_regions) or 1.0)
            for mcc_region in mcc_regions:
                regions.append((mcc_region, score))
            if len(mcc_regions) > 1:
                ambiguous_cells.append(cell)

        # Group by region code
        grouped_regions = {}
        for region, score in regions:
            code = region.code
            if code not in grouped_regions:
                grouped_regions[code] = [region, score]
            else:
                # Sum up scores of multiple matches
                grouped_regions[code][1] += score

        if ambiguous_cells:
            # Only do a database query if the mcc is ambiguous.
            # Use the area models for area and cell entries,
            # as we are only interested in the region here,
            # which won't differ between individual cells inside and area.
            areas = query_areas(
                query, ambiguous_cells, self.area_model, self.raven_client)
            for area in areas:
                code = area.region
                if code and code in grouped_regions:
                    grouped_regions[code][1] += area.score(now)

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
        results = self.search_cell(query)
        query.emit_source_stats(self.source, results)
        return results


class OCIDPositionSource(CellPositionSource):
    """Implements a search using the :term:`OCID` cell data."""

    cell_model = CellOCID
    area_model = CellAreaOCID
    fallback_field = None  #:
    source = DataSource.ocid  #:
