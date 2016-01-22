"""Implementation of a GeoIP based search source."""

from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.source import (
    PositionSource,
    RegionSource,
    Source,
)


class GeoIPSource(Source):
    """A GeoIPSource returns search results based on a GeoIP database."""

    fallback_field = 'ipf'
    source = DataSource.geoip
    geoip_accuracy_field = 'radius'

    def should_search(self, query, results):
        should = super(GeoIPSource, self).should_search(query, results)
        if should and query.ip:
            return True
        return False

    def search(self, query):
        results = self.result_list()

        # The GeoIP record is already available on the query object,
        # there's no need to do a lookup again.
        geoip = query.geoip
        if geoip:
            results.add(self.result_type(
                lat=geoip['latitude'],
                lon=geoip['longitude'],
                accuracy=geoip[self.geoip_accuracy_field],
                region_code=geoip['region_code'],
                region_name=geoip['region_name'],
                score=geoip['score'],
            ))

        query.emit_source_stats(self.source, results)
        return results


class GeoIPPositionSource(GeoIPSource, PositionSource):
    """A GeoIPSource returning position results."""


class GeoIPRegionSource(GeoIPSource, RegionSource):
    """A GeoIPSource returning region results."""

    geoip_accuracy_field = 'region_radius'
