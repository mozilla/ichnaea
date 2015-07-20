from ichnaea.api.locate.result import (
    Country,
    Position,
)
from ichnaea.tests.base import TestCase


class TestPosition(TestCase):

    def test_found_when_lat_lon_set(self):
        position = Position(lat=1.0, lon=1.0)
        self.assertTrue(position.found())

    def test_not_found_when_lat_or_lon_is_None(self):
        for (lat, lon) in ((1.0, None), (None, 1.0), (None, None)):
            position = Position(lat=lat, lon=lon)
            self.assertFalse(position.found())

    def test_agrees_with_other_when_distance_within_accuracy(self):
        position1 = Position(lat=1.0, lon=1.0, accuracy=1000)
        position2 = Position(lat=1.001, lon=1.001, accuracy=1000)
        self.assertTrue(position1.agrees_with(position2))

    def test_does_not_agree_with_other_outside_accuracy(self):
        position1 = Position(lat=1.0, lon=1.0, accuracy=100)
        position2 = Position(lat=1.001, lon=1.001, accuracy=100)
        self.assertFalse(position1.agrees_with(position2))

    def test_never_accurate_enough(self):
        position = Position()
        self.assertFalse(position.accurate_enough())

    def test_not_more_accurate_if_not_found(self):
        position1 = Position(lat=1.0, lon=1.0)
        position2 = Position()
        self.assertFalse(position2.more_accurate(position1))

    def test_more_accurate_if_other_not_found(self):
        position1 = Position(lat=1.0, lon=1.0)
        position2 = Position()
        self.assertTrue(position1.more_accurate(position2))

    def test_more_accurate_if_from_preferred_source(self):
        position1 = Position(lat=1.0, lon=1.0, source=1)
        position2 = Position(lat=1.0, lon=1.0, source=2)
        self.assertTrue(position1.more_accurate(position2))

    def test_more_accurate_if_agrees_and_lower_accuracy(self):
        position1 = Position(lat=1.0, lon=1.0, accuracy=500)
        position2 = Position(lat=1.0, lon=1.0, accuracy=1000)
        self.assertTrue(position1.more_accurate(position2))


class TestCountry(TestCase):

    def test_found_when_country_code_and_name_set(self):
        country = Country(country_code='CA', country_name='Canada')
        self.assertTrue(country.found())

    def test_not_found_when_country_code_or_name_missing(self):
        for (country_code, country_name) in (
                ('CA', None), (None, 'Canada'), (None, None)):
            country = Country(
                country_code=country_code, country_name=country_name)
            self.assertFalse(country.found())

    def test_agrees_with_same_country_code(self):
        country1 = Country(country_code='CA')
        country2 = Country(country_code='CA')
        self.assertTrue(country1.agrees_with(country2))

    def test_not_agrees_with_different_country_code(self):
        country1 = Country(country_code='CA')
        country2 = Country(country_code='DE')
        self.assertFalse(country1.agrees_with(country2))

    def test_accurate_enough_if_found(self):
        country = Country(country_code='CA', country_name='Canada')
        self.assertTrue(country.accurate_enough())

    def test_not_accurate_enough_if_not_found(self):
        country = Country()
        self.assertFalse(country.accurate_enough())

    def test_not_more_accurate_if_not_found(self):
        country1 = Country(country_code='CA', country_name='Canada')
        country2 = Country()
        self.assertFalse(country2.more_accurate(country1))

    def test_more_accurate_if_other_not_found(self):
        country1 = Country(country_code='CA', country_name='Canada')
        country2 = Country()
        self.assertTrue(country1.more_accurate(country2))

    def test_more_accurate_if_from_preferred_source(self):
        country1 = Country(country_code='CA', country_name='Canada', source=1)
        country2 = Country(country_code='CA', country_name='Canada', source=2)
        self.assertTrue(country1.more_accurate(country2))

    def test_not_more_accurate_if_from_same_source_and_same_value(self):
        country1 = Country(country_code='CA', country_name='Canada', source=1)
        country2 = Country(country_code='CA', country_name='Canada', source=1)
        self.assertFalse(country1.more_accurate(country2))
