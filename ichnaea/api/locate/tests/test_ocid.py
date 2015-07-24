from ichnaea.api.locate.ocid import OCIDPositionSource
from ichnaea.api.locate.tests.base import BaseSourceTest
from ichnaea.tests.factories import (
    OCIDCellAreaFactory,
    OCIDCellFactory,
)


class TestOCIDPositionSource(BaseSourceTest):

    TestSource = OCIDPositionSource

    def test_check_empty(self):
        query = self.model_query()
        result = self.source.result_type()
        self.assertFalse(self.source.should_search(query, result))

    def test_empty(self):
        query = self.model_query()
        with self.db_call_checker() as check_db_calls:
            result = self.source.search(query)
            self.check_model_result(result, None)
            check_db_calls(rw=0, ro=0)

    def test_cell(self):
        cell = OCIDCellFactory()
        self.session.flush()
        query = self.model_query(cells=[cell])
        result = self.source.search(query)
        self.check_model_result(result, cell)

    def test_cell_ara(self):
        cell = OCIDCellAreaFactory()
        self.session.flush()
        query = self.model_query(cells=[cell])
        result = self.source.search(query)
        self.check_model_result(result, cell)
