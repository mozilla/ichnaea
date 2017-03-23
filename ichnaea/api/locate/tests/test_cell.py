from ichnaea.api.locate.cell import (
    CellPositionMixin,
)
from ichnaea.api.locate.constants import (
    CELL_MAX_ACCURACY,
    CELLAREA_MIN_ACCURACY,
    DataSource,
)
from ichnaea.api.locate.score import (
    area_score,
    station_score,
)
from ichnaea.api.locate.source import PositionSource
from ichnaea.api.locate.tests.base import BaseSourceTest
from ichnaea.tests.factories import (
    CellAreaFactory,
    CellShardFactory,
)
from ichnaea import util


class CellTestPositionSource(CellPositionMixin, PositionSource):

    fallback_field = None
    source = DataSource.internal

    def should_search(self, query, results):
        return self.should_search_cell(query, results)

    def search(self, query):
        results = self.search_cell(query)
        query.emit_source_stats(self.source, results)
        return results


class TestCellPosition(BaseSourceTest):

    Source = CellTestPositionSource

    def test_check_empty(self, geoip_db, http_session, session, source, stats):
        query = self.model_query(
            geoip_db, http_session, session, stats)
        results = source.result_list()
        assert not source.should_search(query, results)

    def test_empty(self, geoip_db, http_session,
                   session_tracker, session, source, stats):
        query = self.model_query(
            geoip_db, http_session, session, stats)
        results = source.search(query)
        self.check_model_results(results, None)
        session_tracker(0)

    def test_cell(self, geoip_db, http_session, session, source, stats):
        now = util.utcnow()
        cell = CellShardFactory(samples=10)
        session.flush()

        query = self.model_query(
            geoip_db, http_session, session, stats,
            cells=[cell])
        results = source.search(query)
        self.check_model_results(results, [cell])
        assert results.best().score == station_score(cell, now)

    def test_cell_wrong_cid(self, geoip_db, http_session,
                            session, source, stats):
        cell = CellShardFactory()
        session.flush()
        cell.cid += 1

        query = self.model_query(
            geoip_db, http_session, session, stats,
            cells=[cell])
        results = source.search(query)
        self.check_model_results(results, None)

    def test_multiple_cells(self, geoip_db, http_session,
                            session, source, stats):
        now = util.utcnow()
        cell = CellShardFactory(samples=100)
        cell2 = CellShardFactory(radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc,
                                 lac=cell.lac, cid=cell.cid + 1,
                                 lat=cell.lat + 1.0, lon=cell.lon + 1.0,
                                 samples=10)
        session.flush()

        query = self.model_query(
            geoip_db, http_session, session, stats,
            cells=[cell, cell2])
        results = source.search(query)
        self.check_model_results(
            results, [cell],
            lat=cell.lat + 0.3333333, lon=cell.lon + 0.3333333,
            accuracy=CELL_MAX_ACCURACY)
        assert (results.best().score ==
                station_score(cell, now) + station_score(cell2, now))

    def test_incomplete_keys(self, geoip_db, http_session,
                             session_tracker, session, source, stats):
        cells = CellAreaFactory.build_batch(4)
        cells[0].radio = None
        cells[1].mcc = None
        cells[2].mnc = None
        cells[3].lac = None

        query = self.model_query(
            geoip_db, http_session, session, stats,
            cells=cells)
        results = source.result_list()
        assert not source.should_search(query, results)
        session_tracker(0)

    def test_smallest_area(self, geoip_db, http_session,
                           session, source, stats):
        now = util.utcnow()
        area = CellAreaFactory(radius=25000, num_cells=8)
        area2 = CellAreaFactory(radius=30000, lat=area.lat + 0.2, num_cells=6)
        session.flush()

        query = self.model_query(
            geoip_db, http_session, session, stats,
            cells=[area, area2])
        results = source.search(query)
        self.check_model_results(results, [area])
        assert results.best().score == area_score(area, now)

    def test_minimum_radius(self, geoip_db, http_session,
                            session, source, stats):
        areas = CellAreaFactory.create_batch(2)
        areas[0].radius = CELLAREA_MIN_ACCURACY - 2000
        areas[1].radius = CELLAREA_MIN_ACCURACY + 3000
        areas[1].lat = areas[0].lat + 0.2
        session.flush()

        query = self.model_query(
            geoip_db, http_session, session, stats,
            cells=areas)
        results = source.search(query)
        self.check_model_results(
            results, [areas[0]], accuracy=CELLAREA_MIN_ACCURACY)
