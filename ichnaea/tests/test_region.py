from ichnaea.models.constants import ALL_VALID_MCCS
from ichnaea.region import (
    _RADIUS_CACHE,
    GEOCODER,
    region_max_radius,
)
from ichnaea.tests.base import TestCase


class TestGeocoder(TestCase):

    def test_no_region(self):
        func = GEOCODER.region
        self.assertEqual(func(-60.0, 11.0), None)
        self.assertEqual(func(0.0, 0.0), None)
        self.assertEqual(func(36.4173, 18.728), None)
        self.assertEqual(func(48.3, -7.0), None)

    def test_region(self):
        func = GEOCODER.region
        self.assertEqual(func(31.522, 34.455), 'XW')
        self.assertEqual(func(42.83256, 20.34221), 'XK')
        self.assertEqual(func(46.2130, 6.1290), 'FR')
        self.assertEqual(func(46.5743, 6.3532), 'CH')
        self.assertEqual(func(48.8656, 13.6781), 'DE')
        self.assertEqual(func(49.7089, 6.0741), 'LU')
        self.assertEqual(func(51.5142, -0.0931), 'GB')
        self.assertEqual(func(60.1, 20.0), 'FI')

    def test_in_region(self):
        func = GEOCODER.in_region
        self.assertTrue(func(51.5142, -0.0931, 'GB'))
        self.assertFalse(func(0.0, 0.0, 'GB'))
        self.assertFalse(func(60.1, 20.0, 'AX'))

    def test_in_region_mcc(self):
        func = GEOCODER.in_region_mcc
        self.assertTrue(func(51.5142, -0.0931, 234))
        self.assertTrue(func(51.5142, -0.0931, 235))
        self.assertFalse(func(0.0, 0.0, 234))

    def test_region_for_cell(self):
        func = GEOCODER.region_for_cell
        self.assertEqual(func(51.5142, -0.0931, 234), 'GB')
        self.assertEqual(func(51.5142, -0.0931, 235), 'GB')
        self.assertEqual(func(46.2130, 6.1290, 228), 'CH')
        self.assertEqual(func(46.5743, 6.3532, 208), 'FR')
        self.assertEqual(func(31.522, 34.455, 425), 'XW')
        self.assertEqual(func(0.0, 0.0, 234), None)


class TestRegionMaxRadius(TestCase):

    li_radius = 13000.0
    usa_radius = 2826000.0
    vat_radius = 1000.0

    def test_alpha2(self):
        r = region_max_radius('US')
        self.assertEqual(r, self.usa_radius)
        cached = _RADIUS_CACHE['US']
        self.assertEqual(r, cached)

        r = region_max_radius('us')
        self.assertEqual(r, self.usa_radius)
        self.assertFalse('us' in _RADIUS_CACHE)

    def test_alpha3(self):
        r = region_max_radius('USA')
        self.assertEqual(r, self.usa_radius)
        cached = _RADIUS_CACHE['USA']
        self.assertEqual(r, cached)

        r = region_max_radius('usa')
        self.assertEqual(r, self.usa_radius)
        self.assertFalse('usa' in _RADIUS_CACHE)

    def test_small_regions(self):
        r = region_max_radius('LI')
        self.assertEqual(r, self.li_radius)
        r = region_max_radius('VAT')
        self.assertEqual(r, self.vat_radius)

    def test_malformed_region(self):
        r = region_max_radius(None)
        self.assertTrue(r is None)

        r = region_max_radius(42)
        self.assertTrue(r is None)

        r = region_max_radius('A')
        self.assertTrue(r is None)

        r = region_max_radius('-#1-')
        self.assertTrue(r is None)

    def test_unknown_region(self):
        r = region_max_radius('AA')
        self.assertTrue(r is None)
        self.assertFalse('AA' in _RADIUS_CACHE)

        r = region_max_radius('AAA')
        self.assertTrue(r is None)
        self.assertFalse('AAA' in _RADIUS_CACHE)


class TestRegionsForMcc(TestCase):

    def test_no_match(self):
        self.assertEqual(GEOCODER.regions_for_mcc(1), [])
        self.assertEqual(GEOCODER.regions_for_mcc(1, names=True), [])

    def test_single(self):
        regions = GEOCODER.regions_for_mcc(262)
        self.assertEqual(set(regions), set(['DE']))
        regions = GEOCODER.regions_for_mcc(262, names=True)
        self.assertEqual(set([r.alpha2 for r in regions]), set(['DE']))

    def test_multiple(self):
        regions = GEOCODER.regions_for_mcc(311)
        self.assertEqual(set(regions), set(['GU', 'US']))
        regions = GEOCODER.regions_for_mcc(311, names=True)
        self.assertEqual(set([r.alpha2 for r in regions]), set(['GU', 'US']))

    def test_filtered(self):
        # AX / Aland Islands is not in the GENC list
        regions = GEOCODER.regions_for_mcc(244)
        self.assertEqual(set(regions), set(['FI']))

    def test_all_valid_mcc(self):
        for mcc in ALL_VALID_MCCS:
            regions = set(GEOCODER.regions_for_mcc(mcc))
            self.assertNotEqual(regions, set())
            self.assertEqual(regions - GEOCODER._valid_regions, set())
