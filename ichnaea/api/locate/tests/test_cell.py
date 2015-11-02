from ichnaea.api.locate.cell import (
    CellPositionSource,
    OCIDPositionSource,
)
from ichnaea.api.locate.constants import (
    CELL_MAX_ACCURACY,
    CELLAREA_MIN_ACCURACY,
)
from ichnaea.api.locate.result import ResultList
from ichnaea.api.locate.tests.base import BaseSourceTest
from ichnaea.tests.factories import (
    CellAreaFactory,
    CellAreaOCIDFactory,
    CellFactory,
    CellOCIDFactory,
)


class TestCellPosition(BaseSourceTest):

    TestSource = CellPositionSource

    def test_check_empty(self):
        query = self.model_query()
        result = self.source.result_type()
        self.assertFalse(self.source.should_search(query, ResultList(result)))

    def test_empty(self):
        query = self.model_query()
        with self.db_call_checker() as check_db_calls:
            result = self.source.search(query)
            self.check_model_result(result, None)
            check_db_calls(rw=0, ro=0)

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
                            lat=cell.lat + 1.0, lon=cell.lon + 1.0)
        self.session.flush()

        query = self.model_query(cells=[cell, cell2])
        result = self.source.search(query)
        self.check_model_result(
            result, cell,
            lat=cell.lat + 0.5, lon=cell.lon + 0.5,
            accuracy=CELL_MAX_ACCURACY)

    def test_incomplete_keys(self):
        cells = CellAreaFactory.build_batch(4)
        cells[0].radio = None
        cells[1].mcc = None
        cells[2].mnc = None
        cells[3].lac = None

        with self.db_call_checker() as check_db_calls:
            query = self.model_query(cells=cells)
            result = self.source.result_type()
            self.assertFalse(
                self.source.should_search(query, ResultList(result)))
            check_db_calls(rw=0, ro=0)

    def test_smallest_area(self):
        area = CellAreaFactory(radius=25000)
        area2 = CellAreaFactory(radius=30000, lat=area.lat + 0.2)
        self.session.flush()

        query = self.model_query(cells=[area, area2])
        result = self.source.search(query)
        self.check_model_result(result, area)

    def test_minimum_radius(self):
        areas = CellAreaFactory.create_batch(2)
        areas[0].radius = CELLAREA_MIN_ACCURACY - 2000
        areas[1].radius = CELLAREA_MIN_ACCURACY + 3000
        areas[1].lat = areas[0].lat + 0.2
        self.session.flush()

        query = self.model_query(cells=areas)
        result = self.source.search(query)
        self.check_model_result(
            result, areas[0],
            accuracy=CELLAREA_MIN_ACCURACY)


class TestOCIDPositionSource(BaseSourceTest):

    TestSource = OCIDPositionSource

    def test_check_empty(self):
        query = self.model_query()
        result = self.source.result_type()
        self.assertFalse(self.source.should_search(query, ResultList(result)))

    def test_empty(self):
        query = self.model_query()
        with self.db_call_checker() as check_db_calls:
            result = self.source.search(query)
            self.check_model_result(result, None)
            check_db_calls(rw=0, ro=0)

    def test_cell(self):
        cell = CellOCIDFactory()
        self.session.flush()
        query = self.model_query(cells=[cell])
        result = self.source.search(query)
        self.check_model_result(result, cell)

    def test_cell_ara(self):
        cell = CellAreaOCIDFactory()
        self.session.flush()
        query = self.model_query(cells=[cell])
        result = self.source.search(query)
        self.check_model_result(result, cell)
