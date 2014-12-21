from collections import namedtuple
import socket

import pygeoip
from pygeoip import GeoIPError
from pygeoip.const import (
    CITY_EDITIONS,
    MEMORY_CACHE,
    STANDARD,
)
from pygeoip.util import ip2long

from ichnaea.constants import (
    DEGREE_DECIMAL_PLACES,
    GEOIP_CITY_ACCURACY,
    GEOIP_COUNTRY_ACCURACY,
)
from ichnaea.geocalc import maximum_country_radius


Country = namedtuple('Country', 'code name')


def radius_from_geoip(record):
    """
    Returns the best accuracy guess in meters for the given GeoIP record
    and whether or not the record included city data.
    """
    accuracy = None
    if 'country_code3' in record and record['country_code3']:
        accuracy = maximum_country_radius(record['country_code3'])
    elif 'country_code' in record and record['country_code']:
        accuracy = maximum_country_radius(record['country_code'])
    if accuracy is None:  # pragma: no cover
        # No country code or no successful radius lookup
        accuracy = GEOIP_COUNTRY_ACCURACY

    city = False
    if 'city' in record and record['city']:
        # Use country radius as an upper bound for city radius
        # for really small countries
        accuracy = min(GEOIP_CITY_ACCURACY, accuracy)
        city = True

    return (accuracy, city)


def configure_geoip(registry_settings=None, filename=None, heka_client=None):
    if registry_settings is None:
        registry_settings = {}

    # Allow tests to override what's defined in settings
    if '_geoip_db' in registry_settings:
        return registry_settings['_geoip_db']

    if filename is None:
        filename = registry_settings.get('geoip_db_path', None)

    if filename is None:
        # No DB file specified in the config
        if heka_client is not None:
            heka_client.raven('No geoip filename specified.')
        return GeoIPNull()

    try:
        # Use a memory cache to avoid changes to the underlying files from
        # causing errors. Also disable class level caching.
        db = GeoIPWrapper(filename, flags=MEMORY_CACHE, cache=False)
        # Actually initialize the memory cache, by doing one fake look-up
        db.geoip_lookup('127.0.0.1')
    except (IOError, GeoIPError):
        # Error opening the database file, maybe it doesn't exist
        if heka_client is not None:
            heka_client.raven('Error opening geoip database file.')
        return GeoIPNull()

    return db


class GeoIPWrapper(pygeoip.GeoIP):

    def __init__(self, filename, flags=STANDARD, cache=True):
        """
        A wrapper around the pygeoip.GeoIP class with two lookup functions
        which return `None` instead of raising errors.
        """
        super(GeoIPWrapper, self).__init__(filename, flags=flags, cache=cache)

        if self._databaseType not in CITY_EDITIONS:
            message = 'Invalid database type, expected City'
            raise GeoIPError(message)

    def _ip2long(self, addr):
        try:
            ipnum = ip2long(addr)
        except socket.error:
            # socket.error: Almost certainly an invalid IP address
            return None
        return ipnum

    def geoip_lookup(self, addr):
        """
        Returns a dictionary with city data, same as the `record_by_addr`
        method.

        This method returns `None` instead of throwing exceptions in
        case of invalid or unknown addresses.

        :arg addr: IP address (e.g. 203.0.113.30)
        """
        ipnum = self._ip2long(addr)
        if not ipnum:
            # invalid IP address
            return None

        try:
            record = self._get_record(ipnum)
        except AttributeError:  # pragma: no cover
            # AttributeError: The GeoIP database has no data for that IP
            return None

        # Translate "no data found" in the unlikely case that it's returned by
        # pygeoip
        if not record:
            return None

        # Round lat/lon to a standard maximum precision
        for i in ('latitude', 'longitude'):
            record[i] = round(record[i], DEGREE_DECIMAL_PLACES)

        return record

    def country_lookup(self, addr):
        """
        Returns a country code and name for an IP address.

        Returns `None` for invalid or unknown addresses.

        :arg addr: IP address (e.g. 203.0.113.30)
        """
        record = self.geoip_lookup(addr)
        if not record:
            return None

        return Country(record['country_code'].upper(), record['country_name'])


class GeoIPNull(object):

    def geoip_lookup(self, addr):
        return None

    def country_lookup(self, addr):
        return None


class GeoIPMock(object):

    def __init__(self, ip_data=None, country_data=None):
        """
        Initialize the mock with a dictionary of records. Each ip record maps
        one IP address string like '127.0.0.1' to a dictionary of data items.
        An example data item is:

        {'127.0.0.1':
            {
                'latitude': 12.34,
                'longitude': 23.45,
                'country_code': 'US',
                'city': True,
            }
        }

        Each country record maps one IP address to a country code and name
        tuple, for example:

        {'127.0.0.1': ('US', 'United States')}
        """
        self.ip_data = ip_data
        self.country_data = country_data

    def geoip_lookup(self, addr_string):
        return self.ip_data.get(addr_string)

    def country_lookup(self, addr_string):  # pragma: no cover
        return self.country_data.get(addr_string)
