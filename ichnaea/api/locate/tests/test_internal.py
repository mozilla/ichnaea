import mobile_codes

from ichnaea.api.locate.internal import (
    InternalCountrySource,
)
from ichnaea.api.locate.tests.base import BaseSourceTest
from ichnaea.tests.factories import (
    CellFactory,
    WifiFactory,
)


class TestCountrySource(BaseSourceTest):

    TestSource = InternalCountrySource
    api_type = 'country'

    def test_country_from_mcc(self):
        country = mobile_codes.mcc('235')[0]
        cell = CellFactory.build(mcc=235)
        query = self.model_query(cells=[cell])
        result = self.source.search(query)
        self.check_model_result(result, country)
        self.check_stats(counter=[
            self.api_type + '.source.test.all.internal.low.hit'])

    def test_ambiguous_mcc(self):
        cell = CellFactory.build(mcc=234)
        query = self.model_query(cells=[cell])
        result = self.source.search(query)
        self.check_model_result(result, None)
        self.check_stats(counter=[
            self.api_type + '.source.test.all.internal.low.miss'])

    def test_wifi(self):
        wifis = WifiFactory.build_batch(2)
        query = self.model_query(wifis=wifis)
        result = self.source.search(query)
        self.check_model_result(result, None)
