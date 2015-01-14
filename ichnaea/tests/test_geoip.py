import tempfile

from maxminddb.const import MODE_AUTO, MODE_MMAP

from ichnaea.constants import (
    GEOIP_CITY_ACCURACY,
    GEOIP_COUNTRY_ACCURACY,
)
from ichnaea import geoip
from ichnaea.geoip import geoip_accuracy
from ichnaea.tests.base import (
    GEOIP_BAD_FILE,
    GeoIPIsolation,
    LogIsolation,
    TestCase,
)


class GeoIPBaseTest(LogIsolation, GeoIPIsolation):

    @classmethod
    def setUpClass(cls):
        super(GeoIPBaseTest, cls).setup_logging()
        super(GeoIPBaseTest, cls).setup_geoip(heka_client=cls.heka_client)

    @classmethod
    def tearDownClass(cls):
        super(GeoIPBaseTest, cls).teardown_geoip()
        super(GeoIPBaseTest, cls).teardown_logging()

    def setUp(self):
        self.clear_log_messages()

    def _open_db(self, filename=None, mode=MODE_AUTO):
        return self.configure_geoip(
            filename=filename, mode=mode, heka_client=self.heka_client)


class TestDatabase(GeoIPBaseTest, TestCase):

    def test_open_ok(self):
        db = self._open_db()
        self.assertIsInstance(db, geoip.GeoIPWrapper)

    def test_age(self):
        db = self._open_db()
        self.assertTrue(isinstance(db.age, int))
        # the test file is older than two months, but not more than 10 years
        self.assertTrue(db.age > 60)
        self.assertTrue(db.age < 3650)

    def test_c_extension(self):
        db = self._open_db()
        self.assertTrue(db.check_extension(),
                        'The C extension was not installed correctly.')

    def test_c_extension_warning(self):
        db = self._open_db(mode=MODE_MMAP)
        self.assertFalse(db.check_extension())
        self.check_expected_heka_messages(
            sentry=[('msg', 'Maxmind C extension not installed.', 1)]
        )

    def test_no_file(self):
        db = self._open_db('')
        self.assertTrue(isinstance(db, geoip.GeoIPNull))
        self.check_expected_heka_messages(
            sentry=[('msg', 'No geoip filename specified.', 1)]
        )

    def test_open_missing_file(self):
        db = self._open_db('/i/taught/i/taw/a/putty/tat')
        self.assertTrue(isinstance(db, geoip.GeoIPNull))
        self.check_expected_heka_messages(
            sentry=[('msg', 'Error opening geoip database file.', 1)]
        )

    def test_open_invalid_file(self):
        with tempfile.NamedTemporaryFile() as temp:
            temp.write('Bucephalus')
            temp.seek(0)
            db = self._open_db(temp.name)
            self.assertTrue(isinstance(db, geoip.GeoIPNull))

        self.check_expected_heka_messages(
            sentry=[('msg', 'Error opening geoip database file.', 1)]
        )

    def test_open_wrong_file_type(self):
        db = self._open_db(GEOIP_BAD_FILE)
        self.assertTrue(isinstance(db, geoip.GeoIPNull))
        self.check_expected_heka_messages(
            sentry=[('msg', 'Error opening geoip database file.', 1)]
        )

    def test_valid_countries(self):
        db = self._open_db()
        for code in ('US', 'GB', 'DE'):
            self.assertTrue(code in db.valid_countries)


class TestGeoIPLookup(GeoIPBaseTest, TestCase):

    def test_ok_city(self):
        london = self.geoip_data['London']
        # Known good value in the wee sample DB we're using
        result = self.geoip_db.geoip_lookup(london['ip'])
        for name in ('latitude', 'longitude'):
            self.assertAlmostEqual(london[name], result[name])
        for name in ('accuracy', 'country_code', 'country_name', 'city'):
            self.assertEqual(london[name], result[name])

    def test_ok_country(self):
        bhutan = self.geoip_data['Bhutan']
        result = self.geoip_db.geoip_lookup(bhutan['ip'])
        for name in ('latitude', 'longitude'):
            self.assertAlmostEqual(bhutan[name], result[name])
        for name in ('accuracy', 'country_code', 'country_name', 'city'):
            self.assertEqual(bhutan[name], result[name])

    def test_fail(self):
        self.assertIsNone(self.geoip_db.geoip_lookup('127.0.0.1'))

    def test_fail_bad_ip(self):
        self.assertIsNone(self.geoip_db.geoip_lookup('546.839.319.-1'))

    def test_with_dummy_db(self):
        self.assertIsNone(geoip.GeoIPNull().geoip_lookup('200'))


class TestCountryLookup(GeoIPBaseTest, TestCase):

    def test_ok_city(self):
        london = self.geoip_data['London']
        # Known good value in the wee sample DB we're using
        code = self.geoip_db.country_lookup(london['ip'])
        self.assertEqual(
            code, (london['country_code'], london['country_name']))

    def test_ok_country(self):
        bhutan = self.geoip_data['Bhutan']
        code = self.geoip_db.country_lookup(bhutan['ip'])
        self.assertEqual(
            code, (bhutan['country_code'], bhutan['country_name']))

    def test_fail(self):
        self.assertIsNone(self.geoip_db.country_lookup('127.0.0.1'))

    def test_fail_bad_ip(self):
        self.assertIsNone(self.geoip_db.country_lookup('546.839.319.-1'))

    def test_with_dummy_db(self):
        self.assertIsNone(geoip.GeoIPNull().country_lookup('200'))

    def test_valid_country(self):
        # open a separate db instance to avoid cross-test pollution
        db = self._open_db()
        db.valid_countries = frozenset(['US', 'DE'])
        london = self.geoip_data['London']
        self.assertIsNone(db.country_lookup(london['ip']))


class TestGeoIPAccuracy(TestCase):

    li_radius = 13000.0
    us_radius = 2826000.0
    va_radius = 1000.0

    def test_country(self):
        accuracy = geoip_accuracy('US')
        self.assertEqual(accuracy, self.us_radius)

    def test_city(self):
        accuracy = geoip_accuracy('US', city=True)
        self.assertEqual(accuracy, GEOIP_CITY_ACCURACY)

    def test_small_country(self):
        accuracy = geoip_accuracy('LI', city=True)
        self.assertEqual(accuracy, self.li_radius)

    def test_tiny_country(self):
        accuracy = geoip_accuracy('VA', city=True)
        self.assertEqual(accuracy, self.va_radius)

    def test_unknown_country(self):
        accuracy = geoip_accuracy('XX')
        self.assertEqual(accuracy, GEOIP_COUNTRY_ACCURACY)

    def test_unknown_city(self):
        accuracy = geoip_accuracy('XX', city=True)
        self.assertEqual(accuracy, GEOIP_CITY_ACCURACY)
