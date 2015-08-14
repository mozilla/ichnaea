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
        results = self.source.search(query)
        self.check_model_result(results, country)
        self.check_stats(counter=[
            (self.api_type + '.source',
                ['key:test', 'country:none', 'source:internal',
                 'accuracy:low', 'status:hit']),
        ])

    def test_ambiguous_mcc(self):
        countries = mobile_codes.mcc('234')
        cell = CellFactory.build(mcc=234)
        query = self.model_query(cells=[cell])
        results = self.source.search(query)
        self.check_model_result(results, countries)
        self.check_stats(counter=[
            (self.api_type + '.source',
                ['key:test', 'country:none', 'source:internal',
                 'accuracy:low', 'status:hit']),
        ])

    def test_wifi(self):
        wifis = WifiFactory.build_batch(2)
        query = self.model_query(wifis=wifis)
        results = self.source.search(query)
        self.check_model_result(results, None)
