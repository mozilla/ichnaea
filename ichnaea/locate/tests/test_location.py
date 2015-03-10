from unittest2 import TestCase

from ichnaea.locate.location import AbstractLocation, PositionLocation, CountryLocation


class TestPositionLocation(TestCase):

    def test_found_when_lat_lon_set(self):
        location = PositionLocation(lat=1.0, lon=1.0)
        self.assertTrue(location.found())

    def test_not_found_when_lat_or_lon_is_None(self):
        for (lat, lon) in ((1.0, None), (None, 1.0), (None, None)):
            location = PositionLocation(lat=lat, lon=lon)
            self.assertFalse(location.found())

    def test_location_agrees_with_other_when_distance_within_accuracy(self):
        location1 = PositionLocation(lat=1.0, lon=1.0, accuracy=1000)
        location2 = PositionLocation(lat=1.001, lon=1.001, accuracy=1000)
        self.assertTrue(location1.agrees_with(location2))

    def test_location_does_not_agree_with_other_outside_accuracy(self):
        location1 = PositionLocation(lat=1.0, lon=1.0, accuracy=100)
        location2 = PositionLocation(lat=1.001, lon=1.001, accuracy=100)
        self.assertFalse(location1.agrees_with(location2))

    def test_position_never_accurate_enough(self):
        location = PositionLocation()
        self.assertFalse(location.accurate_enough())

    def test_not_more_accurate_if_not_found(self):
        location1 = PositionLocation(lat=1.0, lon=1.0)
        location2 = PositionLocation()
        self.assertFalse(location2.more_accurate(location1))

    def test_more_accurate_if_other_not_found(self):
        location1 = PositionLocation(lat=1.0, lon=1.0)
        location2 = PositionLocation()
        self.assertTrue(location1.more_accurate(location2))

    def test_more_accurate_if_from_preferred_source(self):
        location1 = PositionLocation(lat=1.0, lon=1.0, source=1)
        location2 = PositionLocation(lat=1.0, lon=1.0, source=2)
        self.assertTrue(location1.more_accurate(location2))

    def test_more_accurate_if_agrees_and_lower_accuracy(self):
        location1 = PositionLocation(lat=1.0, lon=1.0, accuracy=500)
        location2 = PositionLocation(lat=1.0, lon=1.0, accuracy=1000)
        self.assertTrue(location1.more_accurate(location2))


class TestCountryLocation(TestCase):

    def test_found_when_country_code_and_name_set(self):
        location = CountryLocation(country_code='CA', country_name='Canada')
        self.assertTrue(location.found())

    def test_not_found_when_country_code_or_name_missing(self):
        for (country_code, country_name) in (('CA', None), (None, 'Canada'), (None, None)):
            location = CountryLocation(country_code=country_code, country_name=country_name)
            self.assertFalse(location.found())

    def test_agrees_with_same_country_code(self):
        location1 = CountryLocation(country_code='CA')
        location2 = CountryLocation(country_code='CA')
        self.assertTrue(location1.agrees_with(location2))

    def test_not_agrees_with_different_country_code(self):
        location1 = CountryLocation(country_code='CA')
        location2 = CountryLocation(country_code='DE')
        self.assertFalse(location1.agrees_with(location2))

    def test_accurate_enough_if_found(self):
        location = CountryLocation(country_code='CA', country_name='Canada')
        self.assertTrue(location.accurate_enough())

    def test_not_accurate_enough_if_not_found(self):
        location = CountryLocation()
        self.assertFalse(location.accurate_enough())

    def test_not_more_accurate_if_not_found(self):
        location1 = CountryLocation(country_code='CA', country_name='Canada')
        location2 = CountryLocation()
        self.assertFalse(location2.more_accurate(location1))

    def test_more_accurate_if_other_not_found(self):
        location1 = CountryLocation(country_code='CA', country_name='Canada')
        location2 = CountryLocation()
        self.assertTrue(location1.more_accurate(location2))

    def test_more_accurate_if_from_preferred_source(self):
        location1 = CountryLocation(country_code='CA', country_name='Canada', source=1)
        location2 = CountryLocation(country_code='CA', country_name='Canada', source=2)
        self.assertTrue(location1.more_accurate(location2))

    def test_not_more_accurate_if_from_same_source_and_same_value(self):
        location1 = CountryLocation(country_code='CA', country_name='Canada', source=1)
        location2 = CountryLocation(country_code='CA', country_name='Canada', source=1)
        self.assertFalse(location1.more_accurate(location2))
