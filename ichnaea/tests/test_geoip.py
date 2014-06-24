import os.path
import tempfile

import ichnaea.geoip as geoip
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
            geoip.configure_geoip(filename='/i/taught/i/taw/a/putty/tat')

        with tempfile.NamedTemporaryFile() as temp:
            temp.write('Bucephalus')
            temp.seek(0)
            with self.assertRaises(geoip.GeoIPError):
                geoip.configure_geoip(filename=temp.name)

    def test_open_ok(self):
        result = geoip.configure_geoip(filename=self.filename)
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
