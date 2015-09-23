from ichnaea.constants import ALL_VALID_COUNTRIES
from ichnaea.country import (
    _radius_cache,
    countries_for_mcc,
    country_for_location,
    country_matches_location,
    country_max_radius,
)
from ichnaea.models.constants import ALL_VALID_MCCS
from ichnaea.tests.base import TestCase


class TestCountriesForMcc(TestCase):

    def test_no_match(self):
        self.assertEqual(countries_for_mcc(1), [])

    def test_single(self):
        countries = countries_for_mcc(262)
        self.assertEqual(set([c.alpha2 for c in countries]), set(['DE']))

    def test_multiple(self):
        countries = countries_for_mcc(242)
        self.assertEqual(set([c.alpha2 for c in countries]),
                         set(['BV', 'NO']))

    def test_filtered(self):
        # AX / Aland Islands is not in the GENC list
        countries = countries_for_mcc(244)
        self.assertEqual(set([c.alpha2 for c in countries]), set(['FI']))

    def test_all_valid_mcc(self):
        for mcc in ALL_VALID_MCCS:
            countries = countries_for_mcc(mcc)
            self.assertNotEqual(countries, [])
            codes = set([c.alpha2 for c in countries])
            self.assertEqual(codes - ALL_VALID_COUNTRIES, set())


class TestCountryForLocation(TestCase):

    def test_no_match(self):
        self.assertEqual(country_for_location(0.0, 0.0), None)

    def test_single(self):
        self.assertEqual(country_for_location(51.5142, -0.0931), 'GB')

    def test_multiple(self):
        self.assertEqual(country_for_location(31.522, 34.455), None)

    def test_filtered(self):
        self.assertEqual(country_for_location(60.1, 20.0), None)


class TestCountryMatchesLocation(TestCase):

    def test_hit(self):
        self.assertTrue(country_matches_location(51.5142, -0.0931, 'GB'))

    def test_miss(self):
        self.assertFalse(country_matches_location(0.0, 0.0, 'GB'))

    def test_filtered(self):
        self.assertFalse(country_matches_location(60.1, 20.0, 'AX'))


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
