import tempfile

from maxminddb.const import MODE_MMAP
from six import PY2

from ichnaea.constants import (
    GEOIP_CITY_ACCURACY,
    GEOIP_REGION_ACCURACY,
)
from ichnaea import geoip
from ichnaea.geoip import (
    GEOIP_REGIONS,
    GEOIP_GENC_MAP,
)
from ichnaea.region import GEOCODER
from ichnaea.tests.base import (
    GEOIP_BAD_FILE,
    GeoIPTestCase,
)


class TestDatabase(GeoIPTestCase):

    def test_open(self):
        self.assertIsInstance(self.geoip_db, geoip.GeoIPWrapper)

    def test_age(self):
        self.assertTrue(isinstance(self.geoip_db.age, int))
        # the test file is older than two months, but not more than 10 years
        self.assertTrue(self.geoip_db.age > 60)
        self.assertTrue(self.geoip_db.age < 3650)

    def test_c_extension(self):
        self.assertTrue(self.geoip_db.check_extension(),
                        'The C extension was not installed correctly.')

    def test_c_extension_warning(self):
        db = self._open_db(mode=MODE_MMAP)
        self.assertFalse(db.check_extension())
        self.check_raven(['RuntimeError: Maxmind C extension not installed'])

    def test_no_file(self):
        db = self._open_db('')
        self.assertTrue(isinstance(db, geoip.GeoIPNull))
        self.check_raven(['OSError: No geoip filename specified.'])

    def test_open_missing_file(self):
        db = self._open_db('/i/taught/i/taw/a/putty/tat')
        self.assertTrue(isinstance(db, geoip.GeoIPNull))
        error = 'FileNotFoundError'
        if PY2:
            error = 'IOError'
        self.check_raven([error + ': No such file or directory'])

    def test_open_invalid_file(self):
        with tempfile.NamedTemporaryFile() as temp:
            temp.write(b'Bucephalus')
            temp.seek(0)
            db = self._open_db(temp.name)
            self.assertTrue(isinstance(db, geoip.GeoIPNull))
        self.check_raven(['InvalidDatabaseError: Error opening database file'])

    def test_open_wrong_file_type(self):
        db = self._open_db(GEOIP_BAD_FILE)
        self.assertTrue(isinstance(db, geoip.GeoIPNull))
        self.check_raven(['InvalidDatabaseError: Invalid database type'])

    def test_regions(self):
        valid_regions = GEOCODER.valid_regions
        mapped_regions = set([GEOIP_GENC_MAP.get(r, r) for r in GEOIP_REGIONS])
        self.assertEqual(mapped_regions - valid_regions, set())
        for region in mapped_regions:
            accuracy, region_accuracy = self.geoip_db.accuracy(
                region, default=None)
            self.assertNotEqual(accuracy, None, region)
            self.assertNotEqual(region_accuracy, None, region)


class TestGeoIPLookup(GeoIPTestCase):

    def test_city(self):
        london = self.geoip_data['London']
        # Known good value in the wee sample DB we're using
        result = self.geoip_db.geoip_lookup(london['ip'])
        for name in ('latitude', 'longitude'):
            self.assertAlmostEqual(london[name], result[name])
        for name in ('accuracy', 'region_code', 'region_name', 'city'):
            self.assertEqual(london[name], result[name])

    def test_region(self):
        bhutan = self.geoip_data['Bhutan']
        result = self.geoip_db.geoip_lookup(bhutan['ip'])
        for name in ('latitude', 'longitude'):
            self.assertAlmostEqual(bhutan[name], result[name])
        for name in ('accuracy', 'region_code', 'region_name', 'city'):
            self.assertEqual(bhutan[name], result[name])

    def test_ipv6(self):
        result = self.geoip_db.geoip_lookup('2a02:ffc0::')
        self.assertEqual(result['region_code'], 'GI')
        self.assertEqual(result['region_name'], 'Gibraltar')
        self.assertEqual(result['accuracy'], self.geoip_db.accuracy('GI')[0])

    def test_fail(self):
        self.assertIsNone(self.geoip_db.geoip_lookup('127.0.0.1'))

    def test_fail_bad_ip(self):
        self.assertIsNone(self.geoip_db.geoip_lookup('546.839.319.-1'))

    def test_with_dummy_db(self):
        self.assertIsNone(geoip.GeoIPNull().geoip_lookup('200'))


class TestGeoIPAccuracy(GeoIPTestCase):

    def test_region(self):
        self.assertTrue(self.geoip_db.accuracy('US')[0] > 1000000.0)
        self.assertTrue(self.geoip_db.accuracy('XK')[0] > 50000.0)

    def test_city(self):
        self.assertEqual(
            self.geoip_db.accuracy('US', city=True)[0], GEOIP_CITY_ACCURACY)
        self.assertTrue(
            self.geoip_db.accuracy('LI', city=True)[0] < GEOIP_CITY_ACCURACY)
        self.assertTrue(
            self.geoip_db.accuracy('VA', city=True)[0] < GEOIP_CITY_ACCURACY)

    def test_unknown(self):
        self.assertEqual(
            self.geoip_db.accuracy('XX')[0], GEOIP_REGION_ACCURACY)
        self.assertEqual(
            self.geoip_db.accuracy('XX', city=True)[0], GEOIP_CITY_ACCURACY)
