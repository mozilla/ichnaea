from ichnaea.scripts import region_json
from ichnaea.tests.base import TestCase


class RegionJsonTestCase(TestCase):

    def test_compiles(self):
        self.assertTrue(hasattr(region_json, 'console_entry'))

    def test_guess_code(self):
        self.assertEqual(region_json.guess_code({'adm0_a3_is': 'SJM'}), 'XR')
        self.assertEqual(region_json.guess_code({'iso_a3': 'KOS'}), 'XK')
        self.assertEqual(region_json.guess_code({'iso_a3': 'AUS'}), 'AU')
        self.assertEqual(region_json.guess_code({'iso_a3': 'ATA'}), 'AQ')
        self.assertEqual(region_json.guess_code({'iso_a3': 'XXX'}), None)
