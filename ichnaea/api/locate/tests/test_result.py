from ichnaea.api.locate.constants import DataAccuracy
from ichnaea.api.locate.query import Query
from ichnaea.api.locate.result import (
    Country,
    Position,
    Result,
    ResultList,
)
from ichnaea.tests.base import TestCase
from ichnaea.tests.factories import WifiFactory


class TestResult(TestCase):

    def test_repr(self):
        result = Result(country_code='DE', lat=1.0)
        rep = repr(result)
        self.assertTrue(rep.startswith('Result'), rep)
        self.assertFalse('DE' in rep, rep)
        self.assertFalse('1.0' in rep, rep)

    def test_empty(self):
        self.assertTrue(Result().empty())

    def test_satisfies(self):
        self.assertFalse(Result().satisfies(Query()))

    def test_data_accuracy(self):
        self.assertEqual(Result().data_accuracy, DataAccuracy.none)


class TestResultList(TestCase):

    def test_init(self):
        results = ResultList(Result())
        self.assertEqual(len(results), 1)

    def test_add(self):
        results = ResultList()
        results.add(Result())
        self.assertEqual(len(results), 1)

    def test_add_many(self):
        results = ResultList(Result())
        results.add((Result(), Result()))
        self.assertEqual(len(results), 3)

    def test_len(self):
        results = ResultList()
        results.add(Result())
        results.add(Result())
        self.assertEqual(len(results), 2)

    def test_getitem(self):
        result = Result()
        results = ResultList()
        results.add(result)
        self.assertEqual(results[0], result)

    def test_iterable(self):
        result = Result()
        results = ResultList()
        results.add(result)
        results.add(result)
        for res in results:
            self.assertEqual(res, result)


class TestCountry(TestCase):

    def test_repr(self):
        country = Country(country_code='DE', country_name='Germany')
        rep = repr(country)
        self.assertTrue(rep.startswith('Country'), rep)
        self.assertTrue('DE' in rep, rep)
        self.assertTrue('Germany' in rep, rep)

    def test_empty(self):
        country = Country(
            country_code='DE', country_name='Germany', accuracy=None)
        self.assertTrue(country.empty())
        country = Country(
            country_code='DE', country_name=None, accuracy=100000.0)
        self.assertTrue(country.empty())
        country = Country(
            country_code=None, country_name='Germany', accuracy=100000.0)
        self.assertTrue(country.empty())

    def test_not_empty(self):
        country = Country(
            country_code='DE', country_name='Germany', accuracy=100000.0)
        self.assertFalse(country.empty())

    def test_satisfies(self):
        country = Country(
            country_code='DE', country_name='Germany', accuracy=100000.0)
        self.assertTrue(country.satisfies(Query()))

    def test_satisfies_fail(self):
        country = Country()
        self.assertFalse(country.satisfies(Query()))

    def test_data_accuracy(self):
        self.assertEqual(Country().data_accuracy, DataAccuracy.none)
        country = Country(
            country_code='DE', country_name='Germany', accuracy=100000.0)
        self.assertEqual(country.data_accuracy, DataAccuracy.low)
        country = Country(
            country_code='VA', country_name='Holy See', accuracy=1000.0)
        self.assertEqual(country.data_accuracy, DataAccuracy.high)


class TestPosition(TestCase):

    def test_repr(self):
        position = Position(lat=1.0, lon=-1.1, accuracy=100.0)
        rep = repr(position)
        self.assertTrue(rep.startswith('Position'), rep)
        self.assertTrue('1.0' in rep, rep)
        self.assertTrue('-1.1' in rep, rep)
        self.assertTrue('100.0' in rep, rep)

    def test_empty(self):
        self.assertTrue(Position(lat=1.0, lon=1.0, accuracy=None).empty())
        self.assertTrue(Position(lat=1.0, lon=None, accuracy=1.0).empty())
        self.assertTrue(Position(lat=None, lon=1.0, accuracy=1.0).empty())

    def test_not_empty(self):
        self.assertFalse(Position(lat=1.0, lon=1.0, accuracy=1.0).empty())
        self.assertFalse(Position(lat=0.0, lon=0.0, accuracy=0).empty())

    def test_satisfies(self):
        wifis = WifiFactory.build_batch(2)
        wifi_query = [{'key': wifi.key} for wifi in wifis]
        position = Position(lat=1.0, lon=1.0, accuracy=100.0)
        query = Query(api_type='locate', wifi=wifi_query)
        self.assertTrue(position.satisfies(query))

    def test_satisfies_fail(self):
        wifis = WifiFactory.build_batch(2)
        wifi_query = [{'key': wifi.key} for wifi in wifis]
        position = Position(lat=1.0, lon=1.0, accuracy=1500.0)
        query = Query(api_type='locate', wifi=wifi_query)
        self.assertFalse(position.satisfies(query))

    def test_data_accuracy(self):
        def _position(accuracy=None):
            return Position(lat=1.0, lon=1.0, accuracy=accuracy)

        self.assertEqual(
            _position().data_accuracy, DataAccuracy.none)
        self.assertEqual(
            _position(accuracy=0.0).data_accuracy, DataAccuracy.high)
        self.assertEqual(
            _position(accuracy=100).data_accuracy, DataAccuracy.high)
        self.assertEqual(
            _position(accuracy=30000.0).data_accuracy, DataAccuracy.medium)
        self.assertEqual(
            _position(accuracy=10 ** 6).data_accuracy, DataAccuracy.low)
