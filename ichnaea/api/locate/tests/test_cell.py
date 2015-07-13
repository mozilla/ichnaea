import mobile_codes

from ichnaea.api.locate.tests.test_provider import ProviderTest
from ichnaea.api.locate.cell import (
    CellAreaPositionProvider,
    CellCountryProvider,
    CellPositionProvider,
)
from ichnaea.constants import LAC_MIN_ACCURACY
from ichnaea.tests.factories import (
    CellAreaFactory,
    CellFactory,
)


class TestCellPositionProvider(ProviderTest):

    TestProvider = CellPositionProvider

    def test_locate_with_no_data_returns_none(self):
        query = self.model_query()
        location = self.provider.locate(query)
        self.check_model_location(location, None)

    def test_locate_finds_cell_with_same_cid(self):
        cell = CellFactory()
        self.session.flush()

        query = self.model_query(cells=[cell])
        location = self.provider.locate(query)
        self.check_model_location(location, cell)

    def test_locate_fails_to_find_cell_with_wrong_cid(self):
        cell = CellFactory()
        self.session.flush()
        cell.cid += 1

        query = self.model_query(cells=[cell])
        location = self.provider.locate(query)
        self.check_model_location(location, None, used=True)

    def test_multiple_cells_combined(self):
        cell = CellFactory()
        cell2 = CellFactory(radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc,
                            lac=cell.lac, cid=cell.cid + 1,
                            lat=cell.lat + 0.02, lon=cell.lon + 0.02)
        self.session.flush()

        query = self.model_query(cells=[cell, cell2])
        location = self.provider.locate(query)
        self.check_model_location(
            location, cell,
            lat=cell.lat + 0.01, lon=cell.lon + 0.01)

    def test_no_db_query_for_incomplete_keys(self):
        cells = CellFactory.build_batch(5)
        cells[0].radio = None
        cells[1].mcc = None
        cells[2].mnc = None
        cells[3].lac = None
        cells[4].cid = None

        with self.db_call_checker() as check_db_calls:
            query = self.model_query(cells=cells)
            location = self.provider.locate(query)
            self.check_model_location(location, None)
            check_db_calls(rw=0, ro=0)


class TestCellAreaPositionProvider(ProviderTest):

    TestProvider = CellAreaPositionProvider

    def test_provider_should_not_locate_if_lacf_disabled(self):
        cells = CellFactory.build_batch(2)

        query = self.model_query(
            cells=cells,
            fallbacks={'lacf': False},
        )
        self.check_should_locate(query, False)

    def test_no_db_query_for_incomplete_keys(self):
        cells = CellFactory.build_batch(4)
        cells[0].radio = None
        cells[1].mcc = None
        cells[2].mnc = None
        cells[3].lac = None

        with self.db_call_checker() as check_db_calls:
            query = self.model_query(cells=cells)
            location = self.provider.locate(query)
            self.check_model_location(location, None)
            check_db_calls(rw=0, ro=0)

    def test_shortest_range_lac_used(self):
        area = CellAreaFactory(range=25000)
        area2 = CellAreaFactory(range=30000, lat=area.lat + 0.2)
        self.session.flush()

        query = self.model_query(cells=[area, area2])
        location = self.provider.locate(query)
        self.check_model_location(location, area)

    def test_minimum_range_returned(self):
        areas = CellAreaFactory.create_batch(2)
        areas[0].range = LAC_MIN_ACCURACY - 2000
        areas[1].range = LAC_MIN_ACCURACY + 3000
        areas[1].lat = areas[0].lat + 0.2
        self.session.flush()

        query = self.model_query(cells=areas)
        location = self.provider.locate(query)
        self.check_model_location(
            location, areas[0],
            accuracy=LAC_MIN_ACCURACY)


class TestCellCountryProvider(ProviderTest):

    TestProvider = CellCountryProvider

    def test_locate_finds_country_from_mcc(self):
        country = mobile_codes.mcc('235')[0]
        cell = CellFactory.build(mcc=235)

        query = self.model_query(cells=[cell])
        location = self.provider.locate(query)
        self.check_model_location(location, country)

    def test_mcc_with_multiple_countries_returns_empty_location(self):
        cell = CellFactory.build(mcc=234)

        query = self.model_query(cells=[cell])
        location = self.provider.locate(query)
        self.check_model_location(location, None, used=True)
