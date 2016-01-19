from ichnaea.geocode import GEOCODER
from ichnaea.models.constants import ALL_VALID_MCCS
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
        self.assertEqual(func(42.83256, 20.34221), 'RS')
        self.assertEqual(func(42.4255, 3.3584), 'ES')
        self.assertEqual(func(46.2130, 6.1290), 'FR')
        self.assertEqual(func(46.5743, 6.3532), 'FR')
        self.assertEqual(func(48.8656, 13.6781), 'CZ')
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

    def test_region_for_code(self):
        func = GEOCODER.region_for_code
        self.assertEqual(func('GB').code, 'GB')
        self.assertEqual(func('CH').code, 'CH')
        self.assertEqual(func('XX'), None)
        self.assertEqual(func(None), None)

    def test_max_radius(self):
        self.assertEqual(GEOCODER.region_max_radius('US'), 2971000.0)
        self.assertEqual(GEOCODER.region_max_radius('LI'), 14000.0)
        self.assertEqual(GEOCODER.region_max_radius('VA'), 1000.0)

    def test_max_radius_fail(self):
        for invalid in (None, 42, 'A', 'us', 'USA', 'AA'):
            self.assertTrue(GEOCODER.region_max_radius(invalid) is None)


class TestRegionsForMcc(TestCase):

    def test_no_match(self):
        self.assertEqual(GEOCODER.regions_for_mcc(None), [])
        self.assertEqual(GEOCODER.regions_for_mcc(None, metadata=True), [])
        self.assertEqual(GEOCODER.regions_for_mcc(1), [])
        self.assertEqual(GEOCODER.regions_for_mcc(1, metadata=True), [])
        self.assertEqual(GEOCODER.regions_for_mcc(''), [])
        self.assertEqual(GEOCODER.regions_for_mcc('1', metadata=True), [])

    def test_single(self):
        regions = GEOCODER.regions_for_mcc(262)
        self.assertEqual(set(regions), set(['DE']))
        regions = GEOCODER.regions_for_mcc(262, metadata=True)
        self.assertEqual(set([r.code for r in regions]), set(['DE']))

    def test_multiple(self):
        regions = GEOCODER.regions_for_mcc(311)
        self.assertEqual(set(regions), set(['GU', 'US']))
        regions = GEOCODER.regions_for_mcc(311, metadata=True)
        self.assertEqual(set([r.code for r in regions]), set(['GU', 'US']))

    def test_filtered(self):
        # AX / Aland Islands is not in the GENC list
        regions = GEOCODER.regions_for_mcc(244)
        self.assertEqual(set(regions), set(['FI']))

    def test_all_valid_mcc(self):
        for mcc in ALL_VALID_MCCS:
            regions = set(GEOCODER.regions_for_mcc(mcc))
            self.assertNotEqual(regions, set())
            self.assertEqual(regions - GEOCODER._valid_regions, set())
