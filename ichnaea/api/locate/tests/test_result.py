from ichnaea.api.locate.constants import (
    DataAccuracy,
    DataSource,
)
from ichnaea.api.locate.query import Query
from ichnaea.api.locate.result import (
    Country,
    Result,
    Position,
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

    def test_not_found(self):
        self.assertFalse(Result().found())

    def test_agrees_with(self):
        self.assertTrue(Result().agrees_with(Result()))

    def test_accurate_enough(self):
        self.assertFalse(Result().accurate_enough(Query()))

    def test_more_accurate(self):
        self.assertFalse(Result().more_accurate(Result()))

    def test_data_accuracy(self):
        self.assertEqual(Result().data_accuracy, DataAccuracy.none)


class TestCountry(TestCase):

    def test_repr(self):
        country = Country(country_code='DE', country_name='Germany')
        rep = repr(country)
        self.assertTrue(rep.startswith('Country'), rep)
        self.assertTrue('DE' in rep, rep)
        self.assertTrue('Germany' in rep, rep)

    def test_found(self):
        country = Country(country_code='CA', country_name='Canada')
        self.assertTrue(country.found())

    def test_not_found(self):
        for (country_code, country_name) in (
                ('CA', None), (None, 'Canada'), (None, None)):
            country = Country(
                country_code=country_code, country_name=country_name)
            self.assertFalse(country.found())

    def test_agrees_with(self):
        country1 = Country(country_code='CA')
        country2 = Country(country_code='CA')
        self.assertTrue(country1.agrees_with(country2))

    def test_disagrees_with(self):
        country1 = Country(country_code='CA')
        country2 = Country(country_code='DE')
        self.assertFalse(country1.agrees_with(country2))

    def test_accurate_enough(self):
        country = Country(country_code='CA', country_name='Canada')
        self.assertTrue(country.accurate_enough(Query()))

    def test_not_accurate_enough(self):
        country = Country()
        self.assertFalse(country.accurate_enough(Query()))

    def test_more_accurate_than_empty(self):
        country1 = Country(country_code='CA', country_name='Canada')
        country2 = Country()
        self.assertTrue(country1.more_accurate(country2))

    def test_less_accurate_than_empty(self):
        country1 = Country(country_code='CA', country_name='Canada')
        country2 = Country()
        self.assertFalse(country2.more_accurate(country1))

    def test_more_accurate_source(self):
        country1 = Country(country_code='CA', country_name='Canada',
                           source=DataSource.internal)
        country2 = Country(country_code='CA', country_name='Canada',
                           source=DataSource.ocid)
        self.assertTrue(country1.more_accurate(country2))

    def test_less_accurate_same(self):
        country1 = Country(country_code='CA', country_name='Canada',
                           source=DataSource.internal)
        country2 = Country(country_code='CA', country_name='Canada',
                           source=DataSource.internal)
        self.assertFalse(country1.more_accurate(country2))

    def test_data_accuracy(self):
        self.assertEqual(
            Country().data_accuracy, DataAccuracy.none)
        self.assertEqual(
            Country(country_code='DE', country_name='Germany').data_accuracy,
            DataAccuracy.low)


class TestPosition(TestCase):

    def test_repr(self):
        position = Position(lat=1.0, lon=-1.1, accuracy=100.0)
        rep = repr(position)
        self.assertTrue(rep.startswith('Position'), rep)
        self.assertTrue('1.0' in rep, rep)
        self.assertTrue('-1.1' in rep, rep)
        self.assertTrue('100.0' in rep, rep)

    def test_found(self):
        position = Position(lat=1.0, lon=1.0, accuracy=10.0)
        self.assertTrue(position.found())

    def test_not_found(self):
        for (lat, lon) in ((1.0, None), (None, 1.0), (None, None)):
            position = Position(lat=lat, lon=lon, accuracy=10.0)
            self.assertFalse(position.found())

    def test_agrees_closeby(self):
        position1 = Position(lat=1.0, lon=1.0, accuracy=1000)
        position2 = Position(lat=1.001, lon=1.001, accuracy=1000)
        self.assertTrue(position1.agrees_with(position2))

    def test_does_not_agree_far_away(self):
        position1 = Position(lat=1.0, lon=1.0, accuracy=100)
        position2 = Position(lat=1.001, lon=1.001, accuracy=100)
        self.assertFalse(position1.agrees_with(position2))

    def test_accurate_enough(self):
        wifis = WifiFactory.build_batch(2)
        wifi_query = [{'key': wifi.key} for wifi in wifis]
        position = Position(lat=1.0, lon=1.0, accuracy=100.0)
        query = Query(api_type='locate', wifi=wifi_query)
        self.assertTrue(position.accurate_enough(query))

    def test_not_accurate_enough(self):
        wifis = WifiFactory.build_batch(2)
        wifi_query = [{'key': wifi.key} for wifi in wifis]
        position = Position(lat=1.0, lon=1.0, accuracy=1500.0)
        query = Query(api_type='locate', wifi=wifi_query)
        self.assertFalse(position.accurate_enough(query))

    def test_more_accurate_than_empty(self):
        position1 = Position(lat=1.0, lon=1.0, accuracy=10.0)
        position2 = Position()
        self.assertTrue(position1.more_accurate(position2))

    def test_less_accurate_than_empty(self):
        position1 = Position(lat=1.0, lon=1.0, accuracy=10.0)
        position2 = Position()
        self.assertFalse(position2.more_accurate(position1))

    def test_more_accurate_source(self):
        position1 = Position(lat=1.0, lon=1.0, accuracy=10.0,
                             source=DataSource.internal)
        position2 = Position(lat=1.0, lon=1.0, accuracy=10.0,
                             source=DataSource.ocid)
        self.assertTrue(position1.more_accurate(position2))

    def test_more_accurate_closeby(self):
        position1 = Position(lat=1.0, lon=1.0, accuracy=500)
        position2 = Position(lat=1.0, lon=1.0, accuracy=1000)
        self.assertTrue(position1.more_accurate(position2))

    def test_data_accuracy(self):
        self.assertEqual(
            Position().data_accuracy, DataAccuracy.none)
        self.assertEqual(
            Position(accuracy=0.0).data_accuracy, DataAccuracy.high)
        self.assertEqual(
            Position(accuracy=100).data_accuracy, DataAccuracy.high)
        self.assertEqual(
            Position(accuracy=30000.0).data_accuracy, DataAccuracy.medium)
        self.assertEqual(
            Position(accuracy=10 ** 6).data_accuracy, DataAccuracy.low)
