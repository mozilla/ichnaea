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
    GEOIP_CITY_ACCURACY,
    GEOIP_COUNTRY_ACCURACY,
)
from ichnaea.region import region_max_radius

VALID_COUNTRIES = frozenset([region.alpha2 for region in genc.REGIONS])


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
        db.geoip_lookup('127.0.0.1')
    except (InvalidDatabaseError, IOError, OSError, ValueError):
        # Error opening the database file, maybe it doesn't exist
        if raven_client is not None:
            raven_client.captureException()
        return GeoIPNull()

    return db


def geoip_accuracy(code, city=False):
    """
    Return the best accuracy guess for the given GeoIP record.

    :param code: A two-letter ISO country code.
    :type code: str

    :param city: Do we have a city record or a country record.
    :type city: bool

    :returns: An accuracy guess in meters.
    :rtype: int
    """
    accuracy = None
    if code:
        accuracy = region_max_radius(code)
    if accuracy is None:
        # No country code or no successful radius lookup
        accuracy = GEOIP_COUNTRY_ACCURACY

    if city:
        # Use country radius as an upper bound for city radius
        # for really small countries
        accuracy = min(GEOIP_CITY_ACCURACY, accuracy)

    return accuracy


class GeoIPWrapper(Reader):
    """
    A wrapper around the :class:`geoip2.database.Reader` class with two lookup
    functions which return `None` instead of raising errors.
    """

    lookup_exceptions = (
        AddressNotFoundError, GeoIP2Error, InvalidDatabaseError, ValueError)
    valid_countries = VALID_COUNTRIES  #: A set of valid country codes.

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

    def geoip_lookup(self, addr):
        """
        Look up information for the given IP address.

        :param addr: IP address (e.g. '203.0.113.30')
        :type addr: str

        :returns: A dictionary with city, country data and location data.
        :rtype: dict
        """
        try:
            record = self.city(addr)
        except self.lookup_exceptions:
            # The GeoIP database has no data for this IP or is broken.
            record = None

        if not record:
            return None

        country = record.country
        city = bool(record.city.name)
        location = record.location
        if not (location.latitude and
                location.longitude and
                country.iso_code):  # pragma: no cover
            return None

        return {
            # Round lat/lon to a standard maximum precision
            'latitude': round(location.latitude, DEGREE_DECIMAL_PLACES),
            'longitude': round(location.longitude, DEGREE_DECIMAL_PLACES),
            'country_code': country.iso_code,
            'country_name': country.name,
            'city': city,
            'accuracy': geoip_accuracy(country.iso_code, city=city),
        }


class GeoIPNull(object):
    """
    A dummy implementation of the :class:`~ichnaea.geoip.GeoIPWrapper` API.
    """

    valid_countries = VALID_COUNTRIES  #: A set of valid country codes.

    def geoip_lookup(self, addr):
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
