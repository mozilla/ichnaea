"""Implementation of a search provider using a GeoIP database."""

from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.result import (
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

    def search(self, query):
        # Always consider there to be GeoIP data, even if no
        # client_addr was provided
        result = self.result_type(query_data=True)

        if query.geoip and self.geoip_db is not None:
            geoip = self.geoip_db.geoip_lookup(query.geoip)
            if geoip:
                if geoip['city']:
                    query.stat_count('geoip_city_found')
                else:
                    query.stat_count('geoip_country_found')

                result = self.result_type(
                    lat=geoip['latitude'],
                    lon=geoip['longitude'],
                    accuracy=geoip['accuracy'],
                    country_code=geoip['country_code'],
                    country_name=geoip['country_name'],
                )

        return result


class GeoIPPositionProvider(BaseGeoIPProvider):
    result_type = Position


class GeoIPCountryProvider(BaseGeoIPProvider):
    result_type = Country
