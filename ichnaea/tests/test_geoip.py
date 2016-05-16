import os
import shutil
import tempfile

from maxminddb.const import (
    MODE_AUTO,
    MODE_MMAP,
)
import six

from ichnaea.geocode import GEOCODER
from ichnaea import geoip
from ichnaea.tests import DATA_DIRECTORY

GEOIP_BAD_FILE = os.path.join(
    DATA_DIRECTORY, 'GeoIP2-Connection-Type-Test.mmdb')
GEOIP_TEST_FILE = os.path.join(DATA_DIRECTORY, 'GeoIP2-City-Test.mmdb')


class TestGeoIP(object):

    @classmethod
    def _open_db(cls, raven, filename=GEOIP_TEST_FILE, mode=MODE_AUTO):
        return geoip.configure_geoip(
            filename, mode=mode, raven_client=raven)

    def test_open(self, geoip_db):
        assert isinstance(geoip_db, geoip.GeoIPWrapper)

    def test_age(self, geoip_db):
        assert isinstance(geoip_db.age, int)
        # the test file is older than two months, but not more than 10 years
        assert geoip_db.age > 60
        assert geoip_db.age < 3650

    def test_c_extension(self, geoip_db):
        assert geoip_db.check_extension()

    def test_c_extension_warning(self, raven):
        with self._open_db(raven, mode=MODE_MMAP) as db:
            assert not db.check_extension()
        raven.check(['RuntimeError: Maxmind C extension not installed'])

    def test_no_file(self, raven):
        with self._open_db(raven, '') as db:
            assert isinstance(db, geoip.GeoIPNull)
        raven.check(['OSError: No geoip filename specified.'])

    def test_open_missing_file(self, raven):
        tmpdir = tempfile.mkdtemp()
        try:
            filename = os.path.join(tmpdir, 'not_there')
            with self._open_db(raven, filename) as db:
                assert isinstance(db, geoip.GeoIPNull)
        finally:
            shutil.rmtree(tmpdir)
        if six.PY2:
            raven.check(['IOError: No such file or directory'])
        else:
            raven.check(['FileNotFoundError'])

    def test_open_invalid_file(self, raven):
        with tempfile.NamedTemporaryFile() as temp:
            temp.write(b'Bucephalus')
            temp.seek(0)
            with self._open_db(raven, temp.name) as db:
                assert isinstance(db, geoip.GeoIPNull)
        raven.check(['InvalidDatabaseError: Error opening database file'])

    def test_open_wrong_file_type(self, raven):
        with self._open_db(raven, GEOIP_BAD_FILE) as db:
            assert isinstance(db, geoip.GeoIPNull)
        raven.check(['InvalidDatabaseError: Invalid database type'])

    def test_regions(self, geoip_db):
        valid_regions = GEOCODER.valid_regions
        mapped_regions = set([geoip.GEOIP_GENC_MAP.get(r, r)
                              for r in geoip.REGION_SCORE.keys()])
        assert mapped_regions - valid_regions == set()
        for region in mapped_regions:
            radius, region_radius = geoip_db.radius(
                region, default=None)
            assert radius is not None
            assert region_radius is not None


class TestLookup(object):

    def test_city(self, geoip_data, geoip_db):
        london = geoip_data['London']
        result = geoip_db.lookup(london['ip'])
        for name in ('latitude', 'longitude', 'radius', 'region_radius'):
            assert round(london[name], 7) == result[name]
        for name in ('region_code', 'region_name', 'city', 'score'):
            assert london[name] == result[name]

    def test_region(self, geoip_data, geoip_db):
        bhutan = geoip_data['Bhutan']
        result = geoip_db.lookup(bhutan['ip'])
        for name in ('latitude', 'longitude', 'radius', 'region_radius'):
            assert round(bhutan[name], 7) == result[name]
        for name in ('region_code', 'region_name', 'city', 'score'):
            assert bhutan[name] == result[name]

    def test_ipv6(self, geoip_db):
        result = geoip_db.lookup('2a02:ffc0::')
        assert result['region_code'] == 'GI'
        assert result['region_name'] == 'Gibraltar'
        assert result['radius'] == geoip_db.radius('GI')[0]

    def test_fail(self, geoip_db):
        assert geoip_db.lookup('127.0.0.1') is None

    def test_fail_bad_ip(self, geoip_db):
        assert geoip_db.lookup('546.839.319.-1') is None

    def test_with_dummy_db(self):
        assert geoip.GeoIPNull().lookup('200') is None


class TestRadius(object):

    def test_region(self, geoip_db):
        assert geoip_db.radius('US')[0] > 1000000.0
        assert geoip_db.radius('XK')[0] > 50000.0

    def test_subdivision(self, geoip_db):
        assert geoip_db.radius('RU')[0] > 2000000.0
        assert geoip_db.radius('RU', subs=['A'])[0] < 2000000.0

    def test_city(self, geoip_db):
        assert geoip_db.radius('GB', city=2643743)[0] > geoip.CITY_RADIUS
        assert geoip_db.radius(
            'RU', subs=['A'], city=1)[0] == geoip.CITY_RADIUS
        assert geoip_db.radius('LI', city=1)[0] < geoip.CITY_RADIUS
        assert geoip_db.radius('US', city=1)[0] == geoip.CITY_RADIUS

    def test_unknown(self, geoip_db):
        assert geoip_db.radius('XX')[0] == geoip.REGION_RADIUS
        assert geoip_db.radius('XX', city=1)[0] == geoip.CITY_RADIUS
