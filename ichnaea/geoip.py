import socket

import pygeoip
from pygeoip import GeoIPError

from ichnaea.constants import (
    DEGREE_DECIMAL_PLACES,
    GEOIP_CITY_ACCURACY,
    GEOIP_COUNTRY_ACCURACY,
)
from ichnaea.geocalc import maximum_country_radius


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
    if accuracy is None:
        # No country code or no successful radius lookup
        accuracy = GEOIP_COUNTRY_ACCURACY

    city = False
    if 'city' in record and record['city']:
        # Use country radius as an upper bound for city radius
        # for really small countries
        accuracy = min(GEOIP_CITY_ACCURACY, accuracy)
        city = True

    return (accuracy, city)


def configure_geoip(registry_settings=None, filename=None):
    if registry_settings is None:
        registry_settings = {}

    # Allow tests to override what's defined in settings
    if '_geoip_db' in registry_settings:
        return registry_settings['_geoip_db']

    if filename is None:
        filename = registry_settings.get('geoip_db_path', None)

    if filename is None:
        # No DB file specific in the config, return the dummy object
        # FIXME Really need to log an info/warn here that we aren't using GeoIP
        return GeoIPNull()

    try:
        # Use a memory cache to avoid changes to the underlying files from
        # causing errors. Also disable class level caching.
        db = GeoIPWrapper(filename, flags=pygeoip.MEMORY_CACHE, cache=False)
        # Actually initialize the memory cache, by doing one fake look-up
        db.geoip_lookup('127.0.0.1')
    except IOError as e:
        raise GeoIPError("Failed to open GeoIP database '%s': %s" % (
                         filename, e))

    return db


class GeoIPWrapper(pygeoip.GeoIP):

    def geoip_lookup(self, addr_string):
        try:
            r = self.record_by_addr(addr_string)
        except (socket.error, AttributeError):
            # socket.error: Almost certainly an invalid IP address
            # AttributeError: The GeoIP database has no data for that IP
            return None

        # Translate "no data found" in the unlikely case that it's returned by
        # pygeoip
        if not r:
            return None

        for i in ('latitude', 'longitude'):
            r[i] = round(r[i], DEGREE_DECIMAL_PLACES)

        return r


class GeoIPNull(object):

    def geoip_lookup(self, addr_string):
        return None


class GeoIPMock(object):

    def __init__(self, data):
        """
        Initialize the mock with a dictionary of records. Each record maps
        one IP address string like '127.0.0.1' to a dictionary of data items.
        An example data item is:

        {
            'latitude': 12.34,
            'longitude': 23.45,
            'country_code': 'US',
            'city': True,
        }
        """
        self.data = data

    def geoip_lookup(self, addr_string):
        return self.data.get(addr_string)
