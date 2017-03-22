"""Search implementation using a cell database."""

from collections import defaultdict
import math

import numpy
from sqlalchemy.orm import load_only

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
from ichnaea.api.locate.score import (
    area_score,
    station_score,
)
from ichnaea.api.locate.source import PositionSource
from ichnaea.geocalc import distance
from ichnaea.geocode import GEOCODER
from ichnaea.models import (
    area_id,
    decode_cellarea,
    decode_cellid,
    encode_cellarea,
    encode_cellid,
    CellArea,
    CellShard,
    station_blocked,
)
from ichnaea.models.constants import MIN_CELL_SIGNAL
from ichnaea import util

NETWORK_DTYPE = numpy.dtype([
    ('lat', numpy.double),
    ('lon', numpy.double),
    ('radius', numpy.double),
    ('age', numpy.int32),
    ('signalStrength', numpy.int32),
    ('score', numpy.double),
    ('id', 'S11'),
    ('seen_today', numpy.bool),
])


def cluster_cells(cells, lookups, min_age=0):
    """
    Cluster cells by area.
    """
    now = util.utcnow()
    today = now.date()

    # Create a dict of cell ids mapped to their age and signal strength.
    obs_data = {}
    for lookup in lookups:
        obs_data[decode_cellid(lookup.cellid)] = (
            max(abs(lookup.age or min_age), 1000),
            lookup.signalStrength or MIN_CELL_SIGNAL[lookup.radioType])

    areas = defaultdict(list)
    for cell in cells:
        areas[area_id(cell)].append(cell)

    clusters = []
    for area_cells in areas.values():
        clusters.append(numpy.array([(
            cell.lat, cell.lon, cell.radius,
            obs_data[cell.cellid][0],
            obs_data[cell.cellid][1],
            station_score(cell, now),
            encode_cellid(*cell.cellid),
            bool(cell.last_seen >= today))
            for cell in area_cells],
            dtype=NETWORK_DTYPE))

    return clusters


def cluster_areas(areas, lookups, min_age=0):
    """
    Cluster areas, treat each area as its own cluster.
    """
    now = util.utcnow()
    today = now.date()

    # Create a dict of area ids mapped to their age and signal strength.
    obs_data = {}
    for lookup in lookups:
        obs_data[decode_cellarea(lookup.areaid)] = (
            max(abs(lookup.age or min_age), 1000),
            lookup.signalStrength or MIN_CELL_SIGNAL[lookup.radioType])

    clusters = []
    for area in areas:
        clusters.append(numpy.array([(
            area.lat, area.lon, area.radius,
            obs_data[area.areaid][0],
            obs_data[area.areaid][1],
            area_score(area, now),
            encode_cellarea(*area.areaid),
            bool(area.last_seen >= today))],
            dtype=NETWORK_DTYPE))

    return clusters


def aggregate_cell_position(networks, min_accuracy, max_accuracy):
    """
    Calculate the aggregate position of the user inside the given
    cluster of networks.

    Return the position, an accuracy estimate and a combined score.
    The accuracy is bounded by the min_accuracy and max_accuracy.
    """
    if len(networks) == 1:
        lat = networks[0]['lat']
        lon = networks[0]['lon']
        radius = min(max(networks[0]['radius'], min_accuracy), max_accuracy)
        score = networks[0]['score']
        return (float(lat), float(lon), float(radius), float(score))

    points = numpy.array(
        [(net['lat'], net['lon']) for net in networks],
        dtype=numpy.double)

    weights = numpy.array([
        net['score'] *
        min(math.sqrt(2000.0 / net['age']), 1.0) /
        math.pow(net['signalStrength'], 2)
        for net in networks],
        dtype=numpy.double)

    lat, lon = numpy.average(points, axis=0, weights=weights)
    score = networks['score'].sum()

    # Guess the accuracy as the 95th percentile of the distances
    # from the lat/lon to the positions of all networks.
    distances = numpy.array([
        distance(lat, lon, net['lat'], net['lon'])
        for net in networks], dtype=numpy.double)
    accuracy = min(max(numpy.percentile(distances, 95),
                       min_accuracy), max_accuracy)

    return (float(lat), float(lon), float(accuracy), float(score))


def query_cells(query, lookups, model, raven_client):
    # Given a location query and a list of lookup instances, query the
    # database and return a list of model objects.
    cellids = [lookup.cellid for lookup in lookups]
    if not cellids:  # pragma: no cover
        return []

    # load all fields used in score calculation and those we
    # need for the position
    load_fields = ('lat', 'lon', 'radius', 'region', 'samples',
                   'created', 'modified', 'last_seen',
                   'block_last', 'block_count')
    result = []
    today = util.utcnow().date()

    try:
        shards = defaultdict(list)
        for lookup in lookups:
            shards[model.shard_model(lookup.radioType)].append(lookup.cellid)

        for shard, shard_cellids in shards.items():
            rows = (
                query.session.query(shard)
                             .filter(shard.cellid.in_(shard_cellids),
                                     shard.lat.isnot(None),
                                     shard.lon.isnot(None))
                             .options(load_only(*load_fields))
            ).all()
            result.extend([row for row in rows
                           if not station_blocked(row, today)])
    except Exception:
        raven_client.captureException()

    return result


def query_areas(query, lookups, model, raven_client):
    areaids = [lookup.areaid for lookup in lookups]
    if not areaids:  # pragma: no cover
        return []

    # load all fields used in score calculation and those we
    # need for the position or region
    load_fields = ('lat', 'lon', 'radius', 'region', 'num_cells',
                   'created', 'modified', 'last_seen')
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
                    lat, lon, accuracy, score = aggregate_cell_position(
                        cluster, CELL_MIN_ACCURACY, CELL_MAX_ACCURACY)

                    used_networks = [
                        ('cell', bytes(id_), bool(seen_today)) for
                        id_, seen_today in cluster[['id', 'seen_today']]]

                    results.add(self.result_type(
                        lat=lat, lon=lon, accuracy=accuracy, score=score,
                        used_networks=used_networks))

            if len(results):
                return results

        if query.cell_area:
            areas = query_areas(
                query, query.cell_area, self.area_model, self.raven_client)
            if areas:
                for cluster in cluster_areas(areas, query.cell_area):
                    lat, lon, accuracy, score = aggregate_cell_position(
                        cluster, CELLAREA_MIN_ACCURACY, CELLAREA_MAX_ACCURACY)

                    used_networks = [
                        ('area', bytes(id_), bool(seen_today)) for
                        id_, seen_today in cluster[['id', 'seen_today']]]

                    results.add(self.result_type(
                        lat=lat, lon=lon, accuracy=accuracy, score=score,
                        fallback='lacf', used_networks=used_networks))

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
            code = cell.mobileCountryCode
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
                    grouped_regions[code][1] += area_score(area, now)

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

    This source is only used in tests.
    """

    fallback_field = None  #:
    source = DataSource.internal

    def should_search(self, query, results):
        return self.should_search_cell(query, results)

    def search(self, query):
        results = self.search_cell(query)
        query.emit_source_stats(self.source, results)
        return results
