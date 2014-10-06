import os.path
import tempfile

from ichnaea.constants import GEOIP_CITY_ACCURACY
from ichnaea import geoip
from ichnaea.geoip import radius_from_geoip
from ichnaea.tests.base import (
    TestCase,
    FREMONT_IP,
)


class TestGeoIPFallback(TestCase):

    @property
    def filename(self):
        return os.path.join(os.path.dirname(__file__), 'GeoIPCity.dat')

    def _open_db(self, path=None):
        if path is None:
            path = self.filename
        return geoip.configure_geoip(filename=path)

    def test_open_fail(self):
        # FIXME going to fail at this point due to GeoIPNull
        with self.assertRaises(geoip.GeoIPError):
            self._open_db('/i/taught/i/taw/a/putty/tat')

        with tempfile.NamedTemporaryFile() as temp:
            temp.write('Bucephalus')
            temp.seek(0)
            with self.assertRaises(geoip.GeoIPError):
                self._open_db(temp.name)

    def test_open_ok(self):
        result = self._open_db()
        self.assertIsInstance(result, geoip.GeoIPWrapper)

    def test_lookup_ok(self):
        expected = {
            'area_code': 510,
            'city': 'Fremont',
            'continent': 'NA',
            'country_code': 'US',
            'country_code3': 'USA',
            'country_name': 'United States',
            'dma_code': 807,
            'latitude': 37.5079,
            'longitude': -121.96,
            'metro_code': 'San Francisco, CA',
            'postal_code': '94538',
            'region_code': 'CA',
            'time_zone': 'America/Los_Angeles',
        }

        db = self._open_db()
        # Known good value in the wee sample DB we're using
        r = db.geoip_lookup(FREMONT_IP)
        for i in expected.keys():
            if i in ('latitude', 'longitude'):
                self.assertAlmostEqual(expected[i], r[i])
            else:
                self.assertEqual(expected[i], r[i])

    def test_lookup_fail(self):
        db = self._open_db()
        self.assertIsNone(db.geoip_lookup('127.0.0.1'))

    def test_lookup_fail_bad_ip(self):
        db = self._open_db()
        self.assertIsNone(db.geoip_lookup('546.839.319.-1'))

    def test_lookup_with_dummy_db(self):
        self.assertIsNone(geoip.GeoIPNull().geoip_lookup('200'))


class TestGuessRadius(TestCase):

    li_radius = 13000.0
    usa_radius = 2826000.0
    vat_radius = 1000.0

    def test_alpha2(self):
        a, c = radius_from_geoip({'country_code': 'US'})
        self.assertEqual(a, self.usa_radius)
        self.assertFalse(c)

    def test_alpha3(self):
        a, c = radius_from_geoip({'country_code3': 'USA'})
        self.assertEqual(a, self.usa_radius)
        self.assertFalse(c)

    def test_alpha3_takes_precedence(self):
        a, c = radius_from_geoip({'country_code3': 'USA',
                                  'country_code': 'LI'})
        self.assertEqual(a, self.usa_radius)
        self.assertFalse(c)

    def test_city(self):
        a, c = radius_from_geoip({'country_code3': 'USA',
                                  'city': 'Fremont'})
        self.assertEqual(a, GEOIP_CITY_ACCURACY)
        self.assertTrue(c)

    def test_small_country_alpha2(self):
        a, c = radius_from_geoip({'country_code': 'LI',
                                  'city': 'Vaduz'})
        self.assertEqual(a, self.li_radius)
        self.assertTrue(c)

    def test_small_country_alpha3(self):
        a, c = radius_from_geoip({'country_code3': 'VAT',
                                  'city': 'Vatican City'})
        self.assertEqual(a, self.vat_radius)
        self.assertTrue(c)
