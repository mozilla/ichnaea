"""
Implementation of a location provider using a GeoIP database.
"""

from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.location import (
    Country,
    Position,
)
from ichnaea.api.locate.provider import Provider


class BaseGeoIPProvider(Provider):
    """
    A BaseGeoIPProvider implements a search using
    a GeoIP database lookup.
    """

    fallback_field = 'ipf'
    log_name = 'geoip'
    source = DataSource.GeoIP

    def locate(self, query):
        # Always consider there to be GeoIP data, even if no
        # client_addr was provided
        location = self.location_type(query_data=True)

        if query.geoip and self.geoip_db is not None:
            geoip = self.geoip_db.geoip_lookup(query.geoip)
            if geoip:
                if geoip['city']:
                    self.stat_count('geoip_city_found')
                else:
                    self.stat_count('geoip_country_found')

                location = self.location_type(
                    lat=geoip['latitude'],
                    lon=geoip['longitude'],
                    accuracy=geoip['accuracy'],
                    country_code=geoip['country_code'],
                    country_name=geoip['country_name'],
                )

        return location


class GeoIPPositionProvider(BaseGeoIPProvider):
    location_type = Position


class GeoIPCountryProvider(BaseGeoIPProvider):
    location_type = Country
