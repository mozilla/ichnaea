from ichnaea.api.locate.cell import CellPositionMixin
from ichnaea.api.locate.source import PositionSource
from ichnaea.api.locate.tests.base import BaseSourceTest
from ichnaea.constants import LAC_MIN_ACCURACY
from ichnaea.tests.factories import (
    CellAreaFactory,
    CellFactory,
)


class TestCellPosition(BaseSourceTest):

    class TestSource(CellPositionMixin, PositionSource):

        def search(self, query):
            result = self.result_type()
            if not (query.cell or query.cell_area):
                return result

            for func in (self.search_cell, self.search_cell_area):
                new_result = func(query)
                if new_result.more_accurate(result):
                    result = new_result

                if result.accurate_enough():  # pragma: no cover
                    break

            query.emit_source_stats(self.source, result)
            return result

    def test_empty(self):
        query = self.model_query()
        result = self.source.search(query)
        self.check_model_result(result, None)

    def test_cell(self):
        cell = CellFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        result = self.source.search(query)
        self.check_model_result(result, cell)

    def test_cell_wrong_cid(self):
        cell = CellFactory()
        self.session.flush()
        cell.cid += 1

        query = self.model_query(cells=[cell])
        result = self.source.search(query)
        self.check_model_result(result, None)

    def test_multiple_cells(self):
        cell = CellFactory()
        cell2 = CellFactory(radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc,
                            lac=cell.lac, cid=cell.cid + 1,
                            lat=cell.lat + 0.02, lon=cell.lon + 0.02)
        self.session.flush()

        query = self.model_query(cells=[cell, cell2])
        result = self.source.search(query)
        self.check_model_result(
            result, cell,
            lat=cell.lat + 0.01, lon=cell.lon + 0.01)

    def test_incomplete_keys(self):
        cells = CellAreaFactory.build_batch(4)
        cells[0].radio = None
        cells[1].mcc = None
        cells[2].mnc = None
        cells[3].lac = None

        with self.db_call_checker() as check_db_calls:
            query = self.model_query(cells=cells)
            result = self.source.search(query)
            self.check_model_result(result, None)
            check_db_calls(rw=0, ro=0)

    def test_smallest_area(self):
        area = CellAreaFactory(range=25000)
        area2 = CellAreaFactory(range=30000, lat=area.lat + 0.2)
        self.session.flush()

        query = self.model_query(cells=[area, area2])
        result = self.source.search(query)
        self.check_model_result(result, area)

    def test_minimum_range(self):
        areas = CellAreaFactory.create_batch(2)
        areas[0].range = LAC_MIN_ACCURACY - 2000
        areas[1].range = LAC_MIN_ACCURACY + 3000
        areas[1].lat = areas[0].lat + 0.2
        self.session.flush()

        query = self.model_query(cells=areas)
        result = self.source.search(query)
        self.check_model_result(
            result, areas[0],
            accuracy=LAC_MIN_ACCURACY)
