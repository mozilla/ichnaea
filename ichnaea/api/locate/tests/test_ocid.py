from ichnaea.api.locate.ocid import OCIDPositionSource
from ichnaea.api.locate.tests.base import BaseSourceTest
from ichnaea.tests.factories import (
    OCIDCellAreaFactory,
    OCIDCellFactory,
)


class TestOCIDPositionSource(BaseSourceTest):

    TestSource = OCIDPositionSource

    def test_empty(self):
        query = self.model_query()
        result = self.source.search(query)
        self.check_model_result(result, None)

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
