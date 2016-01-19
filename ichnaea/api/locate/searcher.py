"""
Abstract searcher and concrete position and region searchers each using
multiple sources to satisfy a given query.
"""

from collections import defaultdict

from ichnaea.api.locate.cell import OCIDPositionSource
from ichnaea.api.locate.fallback import FallbackPositionSource
from ichnaea.api.locate.geoip import (
    GeoIPPositionSource,
    GeoIPRegionSource,
)
from ichnaea.api.locate.internal import (
    InternalPositionSource,
    InternalRegionSource,
)
from ichnaea.api.locate.result import (
    Position,
    Region,
)
from ichnaea.constants import DEGREE_DECIMAL_PLACES


def _configure_searcher(klass, settings, geoip_db=None, raven_client=None,
                        redis_client=None, stats_client=None, _searcher=None):
    if _searcher is not None:
        return _searcher
    return klass(settings, geoip_db, raven_client, redis_client, stats_client)


def configure_region_searcher(settings, geoip_db=None, raven_client=None,
                              redis_client=None, stats_client=None,
                              _searcher=None):
    """
    Configure and return a configured
    :class:`~ichnaea.api.locate.searcher.RegionSearcher` instance.

    :param _searcher: Test-only hook to provide a pre-configured searcher.
    """
    return _configure_searcher(
        RegionSearcher, settings, geoip_db=geoip_db,
        raven_client=raven_client, redis_client=redis_client,
        stats_client=stats_client, _searcher=_searcher)


def configure_position_searcher(settings, geoip_db=None, raven_client=None,
                                redis_client=None, stats_client=None,
                                _searcher=None):
    """
    Configure and return a configured
    :class:`~ichnaea.api.locate.searcher.PositionSearcher` instance.

    :param _searcher: Test-only hook to provide a pre-configured searcher.
    """
    return _configure_searcher(
        PositionSearcher, settings, geoip_db=geoip_db,
        raven_client=raven_client, redis_client=redis_client,
        stats_client=stats_client, _searcher=_searcher)


class Searcher(object):
    """
    A Searcher will use a collection of data sources
    to attempt to satisfy a user's query. It will loop over them
    in the order they are specified and use the most accurate result.
    """

    result_type = None  #: :class:`ichnaea.api.locate.result.Result`
    sources = ()  #:
    source_classes = ()  #:

    def __init__(self, settings,
                 geoip_db, raven_client, redis_client, stats_client):
        self.sources = []
        for name, source in self.source_classes:
            source_settings = settings.get_map('locate:%s' % name, {})
            source_instance = source(
                settings=source_settings,
                geoip_db=geoip_db,
                raven_client=raven_client,
                redis_client=redis_client,
                stats_client=stats_client,
            )
            self.sources.append((name, source_instance))

    def _best_result(self, results, query):
        raise NotImplementedError()

    def _search(self, query):
        results = self.result_type().new_list()
        for name, source in self.sources:
            if source.should_search(query, results):
                results.add(source.search(query))

        return self._best_result(results, query)

    def format_result(self, result):
        """
        Converts the result object into a dictionary representation.

        :param result: A query result.
        :type result: :class:`~ichnaea.api.locate.result.Result`
        """
        raise NotImplementedError()

    def search(self, query):
        """
        Provide a type specific query result or return None.

        :param query: A query.
        :type query: :class:`~ichnaea.api.locate.query.Query`

        :returns: A result_type specific dict.
        """
        query.emit_query_stats()
        result = self._search(query)
        query.emit_result_stats(result)
        if not result.empty():
            return self.format_result(result)


class PositionSearcher(Searcher):
    """
    A PositionSearcher will return a position defined by a latitude,
    a longitude and an accuracy in meters.
    """

    result_type = Position
    source_classes = (
        ('geoip', GeoIPPositionSource),
        ('internal', InternalPositionSource),
        ('ocid', OCIDPositionSource),
        ('fallback', FallbackPositionSource),
    )

    def format_result(self, result):
        return {
            'lat': round(result.lat, DEGREE_DECIMAL_PLACES),
            'lon': round(result.lon, DEGREE_DECIMAL_PLACES),
            'accuracy': round(result.accuracy, DEGREE_DECIMAL_PLACES),
            'fallback': result.fallback,
        }

    def _best_result(self, results, query):
        return results.best(query.expected_accuracy)


class RegionSearcher(Searcher):
    """
    A RegionSearcher will return a region name and code.
    """

    result_type = Region
    source_classes = (
        ('internal', InternalRegionSource),
        ('geoip', GeoIPRegionSource),
    )

    def format_result(self, result):
        return {
            'region_code': result.region_code,
            'region_name': result.region_name,
            'fallback': result.fallback,
        }

    def _best_result(self, results, query):
        if len(results) < 2:
            return results.best(query.expected_accuracy)

        # group by region code
        grouped = defaultdict(list)
        for result in results:
            if not result.empty():
                grouped[result.region_code].append(result)

        regions = []
        for code, values in grouped.items():
            region = values[0]
            regions.append((
                sum([value.score for value in values]),
                region.accuracy,
                region))

        # pick the region with the highest combined score,
        # break tie by region with the largest radius
        sorted_regions = sorted(regions, reverse=True)
        return sorted_regions[0][2]
