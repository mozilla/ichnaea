from ichnaea.api.locate.provider import Provider
from ichnaea.api.locate.result import Position
from ichnaea.api.locate.tests.base import BaseSourceTest


class ProviderTest(BaseSourceTest):

    class TestSource(Provider):
        fallback_field = 'ipf'
        result_type = Position


class TestProvider(ProviderTest):

    def test_check_fallback(self):
        query = self.model_query(fallback={})
        self.check_should_search(query, True)

    def test_check_no_fallback(self):
        query = self.model_query(fallback={'ipf': False})
        self.check_should_search(query, False)

    def test_check_different_fallback(self):
        query = self.model_query(fallback={'invalid': False})
        self.check_should_search(query, True)

    def test_check_invalid_fallback(self):
        query = self.model_query(fallback={'ipf': 'asdf'})
        self.check_should_search(query, True)
