import math
import os.path
import socket

from ichnaea.decimaljson import PRECISION
import pygeoip


class GeoIPError(Exception):
    pass


def configure_geoip(registry_settings={}, filename=None):
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
        db = GeoIPWrapper(filename)
    except IOError, e:
        raise GeoIPError("Failed to open GeoIP database \"%s\": %s" % (filename,
                                                                       e))

    return db


class GeoIPWrapper(pygeoip.GeoIP):

    def geoip_lookup(self, addr_string):
        try:
            r = self.record_by_addr(addr_string)
        except (socket.error, AttributeError):
            # socket.error: Almost certainly an invalid IP adress
            # AttributeError: The GeoIP database has no data for that IP
            # FIXME log a warning for an invalid IP?
            return None

        # Translate "no data found" in the unlikely case that it's returned by
        # pygeoip
        if r == {}:
            r = None

        if r:
            for i in ('latitude', 'longitude'):
                r[i] = round(r[i], PRECISION)

        return r


class GeoIPNull(object):

    def geoip_lookup(self, addr_string):
        return None
