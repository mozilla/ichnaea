"""Implementation of a GeoIP based search source."""

from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.source import (
    PositionSource,
    RegionSource,
    Source,
)
from ichnaea.geoip import geoip_accuracy


class GeoIPSource(Source):
    """A GeoIPSource returns search results based on a GeoIP database."""

    fallback_field = 'ipf'
    source = DataSource.geoip

    def _geoip_result_accuracy(self, geoip):
        # use the geoip record, includes city-based accuracy
        return geoip['accuracy']

    def search(self, query):
        result = self.result_type()
        source_used = False

        if query.ip:
            source_used = True

        # The GeoIP record is already available on the query object,
        # there's no need to do a lookup again.
        geoip = query.geoip
        if geoip:
            result = self.result_type(
                lat=geoip['latitude'],
                lon=geoip['longitude'],
                accuracy=self._geoip_result_accuracy(geoip),
                region_code=geoip['region_code'],
                region_name=geoip['region_name'],
            )

        if source_used:
            query.emit_source_stats(self.source, result)

        return result


class GeoIPPositionSource(GeoIPSource, PositionSource):
    """A GeoIPSource returning position results."""


class GeoIPRegionSource(GeoIPSource, RegionSource):
    """A GeoIPSource returning region results."""

    def _geoip_result_accuracy(self, geoip):
        # calculate region based accuracy, ignoring city
        return geoip_accuracy(geoip['region_code'])
