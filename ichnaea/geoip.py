"""
Helper functions and classes around GeoIP lookups, based on Maxmind's
`maxminddb <https://pypi.python.org/pypi/maxminddb>`_ and
`geoip2 <https://pypi.python.org/pypi/geoip2>`_ Python packages.
"""

import time

import genc
from geoip2.database import Reader
from geoip2.errors import (
    AddressNotFoundError,
    GeoIP2Error,
)
from maxminddb import InvalidDatabaseError
from maxminddb.const import MODE_AUTO
from six import PY2

from ichnaea.constants import (
    DEGREE_DECIMAL_PLACES,
    GEOIP_CITY_RADIUS,
    GEOIP_REGION_RADIUS,
)
from ichnaea.geocode import GEOCODER

# The region codes present in the GeoIP data files, extracted from
# the CSV files. Accuracy numbers from October 2015 from
# https://www.maxmind.com/en/geoip2-city-database-accuracy.
# Default value is 0.3 if the website didn't include any data.
GEOIP_SCORE = {
    'AD': 0.3, 'AE': 0.9, 'AF': 0.3, 'AG': 0.3, 'AI': 0.3, 'AL': 0.3,
    'AM': 0.3, 'AO': 0.3, 'AQ': 0.3, 'AR': 0.7, 'AS': 0.3, 'AT': 0.7,
    'AU': 0.7, 'AW': 0.3, 'AX': 0.3, 'AZ': 0.3, 'BA': 0.3, 'BB': 0.3,
    'BD': 0.3, 'BE': 0.8, 'BF': 0.3, 'BG': 0.7, 'BH': 0.3, 'BI': 0.3,
    'BJ': 0.3, 'BL': 0.3, 'BM': 0.3, 'BN': 0.3, 'BO': 0.3, 'BQ': 0.3,
    'BR': 0.7, 'BS': 0.3, 'BT': 0.3, 'BW': 0.3, 'BY': 0.3, 'BZ': 0.3,
    'CA': 0.8, 'CC': 0.3, 'CD': 0.3, 'CF': 0.3, 'CG': 0.3, 'CH': 0.7,
    'CI': 0.3, 'CK': 0.3, 'CL': 0.8, 'CM': 0.3, 'CN': 0.6, 'CO': 0.6,
    'CR': 0.9, 'CU': 0.3, 'CV': 0.3, 'CW': 0.3, 'CX': 0.3, 'CY': 0.3,
    'CZ': 0.8, 'DE': 0.8, 'DJ': 0.3, 'DK': 0.8, 'DM': 0.3, 'DO': 0.3,
    'DZ': 0.3, 'EC': 0.8, 'EE': 0.8, 'EG': 0.7, 'ER': 0.3, 'ES': 0.8,
    'ET': 0.3, 'FI': 0.5, 'FJ': 0.3, 'FK': 0.3, 'FM': 0.3, 'FO': 0.3,
    'FR': 0.7, 'GA': 0.3, 'GB': 0.8, 'GD': 0.3, 'GE': 0.3, 'GF': 0.3,
    'GG': 0.3, 'GH': 0.3, 'GI': 0.3, 'GL': 0.3, 'GM': 0.3, 'GN': 0.3,
    'GP': 0.3, 'GQ': 0.3, 'GR': 0.6, 'GS': 0.3, 'GT': 0.3, 'GU': 0.3,
    'GW': 0.3, 'GY': 0.3, 'HK': 0.9, 'HN': 0.3, 'HR': 0.6, 'HT': 0.3,
    'HU': 0.8, 'ID': 0.7, 'IE': 0.5, 'IL': 0.7, 'IM': 0.3, 'IN': 0.6,
    'IO': 0.3, 'IQ': 0.3, 'IR': 0.3, 'IS': 0.8, 'IT': 0.6, 'JE': 0.3,
    'JM': 0.3, 'JO': 0.3, 'JP': 0.8, 'KE': 0.3, 'KG': 0.3, 'KH': 0.3,
    'KI': 0.3, 'KM': 0.3, 'KN': 0.3, 'KP': 0.3, 'KR': 0.7, 'KW': 0.3,
    'KY': 0.3, 'KZ': 0.3, 'LA': 0.3, 'LB': 0.3, 'LC': 0.3, 'LI': 0.3,
    'LK': 0.3, 'LR': 0.3, 'LS': 0.3, 'LT': 0.7, 'LU': 0.9, 'LV': 0.8,
    'LY': 0.3, 'MA': 0.3, 'MC': 0.3, 'MD': 0.3, 'ME': 0.3, 'MF': 0.3,
    'MG': 0.3, 'MH': 0.3, 'MK': 0.3, 'ML': 0.3, 'MM': 0.3, 'MN': 0.3,
    'MO': 0.3, 'MP': 0.3, 'MQ': 0.3, 'MR': 0.3, 'MS': 0.3, 'MT': 0.9,
    'MU': 0.3, 'MV': 0.3, 'MW': 0.3, 'MX': 0.6, 'MY': 0.7, 'MZ': 0.3,
    'NA': 0.3, 'NC': 0.3, 'NE': 0.3, 'NF': 0.3, 'NG': 0.3, 'NI': 0.3,
    'NL': 0.8, 'NO': 0.8, 'NP': 0.3, 'NR': 0.3, 'NU': 0.3, 'NZ': 0.6,
    'OM': 0.3, 'PA': 0.3, 'PE': 0.8, 'PF': 0.3, 'PG': 0.3, 'PH': 0.5,
    'PK': 0.8, 'PL': 0.6, 'PM': 0.3, 'PN': 0.3, 'PR': 0.9, 'PS': 0.3,
    'PT': 0.7, 'PW': 0.3, 'PY': 0.3, 'QA': 0.9, 'RE': 0.3, 'RO': 0.7,
    'RS': 0.7, 'RU': 0.8, 'RW': 0.3, 'SA': 0.7, 'SB': 0.3, 'SC': 0.3,
    'SD': 0.3, 'SE': 0.7, 'SG': 0.9, 'SH': 0.3, 'SI': 0.8, 'SJ': 0.3,
    'SK': 0.7, 'SL': 0.3, 'SM': 0.3, 'SN': 0.3, 'SO': 0.3, 'SR': 0.3,
    'SS': 0.3, 'ST': 0.3, 'SV': 0.3, 'SX': 0.3, 'SY': 0.3, 'SZ': 0.3,
    'TC': 0.3, 'TD': 0.3, 'TF': 0.3, 'TG': 0.3, 'TH': 0.8, 'TJ': 0.3,
    'TK': 0.3, 'TL': 0.3, 'TM': 0.3, 'TN': 0.3, 'TO': 0.3, 'TR': 0.7,
    'TT': 0.3, 'TV': 0.3, 'TW': 0.8, 'TZ': 0.3, 'UA': 0.7, 'UG': 0.3,
    'UM': 0.3, 'US': 0.8, 'UY': 0.8, 'UZ': 0.3, 'VA': 0.3, 'VC': 0.3,
    'VE': 0.6, 'VG': 0.3, 'VI': 0.3, 'VN': 0.7, 'VU': 0.3, 'WF': 0.3,
    'WS': 0.3, 'XK': 0.3, 'YE': 0.3, 'YT': 0.3, 'ZA': 0.7, 'ZM': 0.3,
    'ZW': 0.3,
}

GEOIP_GENC_MAP = {
    'AX': 'FI',  # Aland Islands -> Finland
    'PS': 'XW',  # Palestine -> West Bank
    'SJ': 'XR',  # Svalbard and Jan Mayen -> Svalbard
    'UM': 'US',  # US Minor Outlying Territories -> US
}


def configure_geoip(filename, mode=MODE_AUTO,
                    raven_client=None, _client=None):
    """
    Configure and return a :class:`~ichnaea.geoip.GeoIPWrapper` instance.

    If no geoip database file of the correct type can be found, return
    a :class:`~ichnaea.geoip.GeoIPNull` dummy implementation instead.

    :param raven_client: A configured raven/sentry client.
    :type raven_client: :class:`raven.base.Client`

    :param _client: Test-only hook to provide a pre-configured client.
    """

    if _client is not None:
        return _client

    if not filename:
        # No DB file specified in the config
        if raven_client is not None:
            try:
                raise OSError('No geoip filename specified.')
            except OSError:
                raven_client.captureException()
        return GeoIPNull()

    try:
        db = GeoIPWrapper(filename, mode=mode)
        if not db.check_extension() and raven_client is not None:
            try:
                raise RuntimeError('Maxmind C extension not installed.')
            except RuntimeError:
                raven_client.captureException()
        # Actually initialize the memory cache, by doing one fake look-up
        db.lookup('127.0.0.1')
    except (InvalidDatabaseError, IOError, OSError, ValueError):
        # Error opening the database file, maybe it doesn't exist
        if raven_client is not None:
            raven_client.captureException()
        return GeoIPNull()

    return db


class GeoIPWrapper(Reader):
    """
    A wrapper around the :class:`geoip2.database.Reader` class with a lookup
    function which returns `None` instead of raising exceptions.
    """

    lookup_exceptions = (
        AddressNotFoundError, GeoIP2Error, InvalidDatabaseError, ValueError)

    def __init__(self, filename, mode=MODE_AUTO):
        """
        Takes the absolute path to a geoip database on the local filesystem
        and an additional mode, which defaults to
        :data:`maxminddb.const.MODE_AUTO`.

        :raises: :exc:`maxminddb.InvalidDatabaseError`
        """
        super(GeoIPWrapper, self).__init__(filename, mode=mode)

        if self.metadata().database_type != 'GeoIP2-City':
            message = 'Invalid database type, expected City'
            raise InvalidDatabaseError(message)

    @property
    def age(self):
        """
        :returns: The age of the database file in days.
        :rtype: int
        """
        build_epoch = self.metadata().build_epoch
        return int(round((time.time() - build_epoch) / 86400, 0))

    def ping(self):
        """
        :returns: True if this is a real database with a valid db file.
        :rtype: bool
        """
        return True

    def check_extension(self):
        """
        :returns: True if the C extension was installed correctly.
        :rtype: bool
        """
        builtin_module = 'builtins'
        if PY2:  # pragma: no cover
            builtin_module = '__builtin__'
        for instance in (self.metadata(), self._db_reader):
            if type(instance).__module__ != builtin_module:
                return False
        return True

    def lookup(self, addr):
        """
        Look up information for the given IP address.

        :param addr: IP address (e.g. '203.0.113.30')
        :type addr: str

        :returns: A dictionary with city, region data and location data.
        :rtype: dict
        """
        try:
            record = self.city(addr)
        except self.lookup_exceptions:
            # The GeoIP database has no data for this IP or is broken.
            record = None

        if not record:
            return None

        region = record.country
        city = bool(record.city.name)
        location = record.location
        if not (location.latitude and
                location.longitude and
                region.iso_code):  # pragma: no cover
            return None

        code = GEOIP_GENC_MAP.get(region.iso_code, region.iso_code).upper()
        radius, region_radius = self.radius(code, city=city)
        score = 0.9
        if city:
            score = GEOIP_SCORE.get(code, 0.3)
        return {
            # Round lat/lon to a standard maximum precision
            'latitude': round(location.latitude, DEGREE_DECIMAL_PLACES),
            'longitude': round(location.longitude, DEGREE_DECIMAL_PLACES),
            'region_code': code,
            'region_name': genc.region_by_alpha2(code).name,
            'city': city,
            'radius': radius,
            'region_radius': region_radius,
            'score': score,
        }

    def radius(self, code, city=False, default=GEOIP_REGION_RADIUS):
        """
        Return the best radius guess for the given region code.

        :param code: A two-letter region code.
        :type code: str

        :param city: Do we have a city record or a region record.
        :type city: bool

        :returns: A tuple of radius/region radius guesses in meters.
        :rtype: tuple
        """
        region_radius = GEOCODER.region_max_radius(code)
        if region_radius is None:
            # No region code or no successful radius lookup
            region_radius = default

        radius = region_radius
        if city:
            # Use region radius as an upper bound for city radius
            # for really small regions. E.g. Vatican City cannot
            # be larger than the Vatican as a region.
            radius = min(GEOIP_CITY_RADIUS, region_radius)

        return (radius, region_radius)


class GeoIPNull(object):
    """
    A dummy implementation of the :class:`~ichnaea.geoip.GeoIPWrapper` API.
    """

    def lookup(self, addr):
        """
        :returns: None
        """
        return None

    @property
    def age(self):
        """
        :returns: -1
        """
        return -1

    def ping(self):
        """
        :returns: False
        """
        return False
