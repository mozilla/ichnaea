from ichnaea.country import (
    _radius_cache,
    country_for_location,
    country_max_radius,
)
from ichnaea.tests.base import TestCase


class TestCountryForLocation(TestCase):

    def test_no_match(self):
        self.assertEqual(country_for_location(0.0, 0.0), None)

    def test_single(self):
        self.assertEqual(country_for_location(51.5142, -0.0931), 'GB')

    def test_multiple(self):
        self.assertEqual(country_for_location(31.522, 34.455), None)


class TestCountryMaxRadius(TestCase):

    li_radius = 13000.0
    usa_radius = 2826000.0
    vat_radius = 1000.0

    def test_alpha2(self):
        r = country_max_radius('US')
        self.assertEqual(r, self.usa_radius)
        cached = _radius_cache['US']
        self.assertEqual(r, cached)

        r = country_max_radius('us')
        self.assertEqual(r, self.usa_radius)
        self.assertFalse('us' in _radius_cache)

    def test_alpha3(self):
        r = country_max_radius('USA')
        self.assertEqual(r, self.usa_radius)
        cached = _radius_cache['USA']
        self.assertEqual(r, cached)

        r = country_max_radius('usa')
        self.assertEqual(r, self.usa_radius)
        self.assertFalse('usa' in _radius_cache)

    def test_small_countries(self):
        r = country_max_radius('LI')
        self.assertEqual(r, self.li_radius)
        r = country_max_radius('VAT')
        self.assertEqual(r, self.vat_radius)

    def test_malformed_country(self):
        r = country_max_radius(None)
        self.assertTrue(r is None)

        r = country_max_radius(42)
        self.assertTrue(r is None)

        r = country_max_radius('A')
        self.assertTrue(r is None)

        r = country_max_radius('-#1-')
        self.assertTrue(r is None)

    def test_unknown_country(self):
        r = country_max_radius('AA')
        self.assertTrue(r is None)
        self.assertFalse('AA' in _radius_cache)

        r = country_max_radius('AAA')
        self.assertTrue(r is None)
        self.assertFalse('AAA' in _radius_cache)
