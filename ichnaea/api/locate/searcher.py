"""
Abstract searcher and concrete position and region searchers each using
multiple sources to satisfy a given query.
"""

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
    PositionResultList,
    Region,
    RegionResultList,
)
from ichnaea.constants import DEGREE_DECIMAL_PLACES


def _configure_searcher(klass, geoip_db=None, raven_client=None,
                        redis_client=None, stats_client=None, _searcher=None):
    if _searcher is not None:
        return _searcher
    return klass(geoip_db, raven_client, redis_client, stats_client)


def configure_region_searcher(geoip_db=None, raven_client=None,
                              redis_client=None, stats_client=None,
                              _searcher=None):
    """
    Configure and return a configured
    :class:`~ichnaea.api.locate.searcher.RegionSearcher` instance.

    :param _searcher: Test-only hook to provide a pre-configured searcher.
    """
    return _configure_searcher(
        RegionSearcher, geoip_db=geoip_db,
        raven_client=raven_client, redis_client=redis_client,
        stats_client=stats_client, _searcher=_searcher)


def configure_position_searcher(geoip_db=None, raven_client=None,
                                redis_client=None, stats_client=None,
                                _searcher=None):
    """
    Configure and return a configured
    :class:`~ichnaea.api.locate.searcher.PositionSearcher` instance.

    :param _searcher: Test-only hook to provide a pre-configured searcher.
    """
    return _configure_searcher(
        PositionSearcher, geoip_db=geoip_db,
        raven_client=raven_client, redis_client=redis_client,
        stats_client=stats_client, _searcher=_searcher)


class Searcher(object):
    """
    A Searcher will use a collection of data sources
    to attempt to satisfy a user's query. It will loop over them
    in the order they are specified and use the best possible result.
    """

    result_list = None  #: :class:`ichnaea.api.locate.result.ResultList`
    result_type = None  #: :class:`ichnaea.api.locate.result.Result`
    sources = ()  #:
    source_classes = ()  #:

    def __init__(self, geoip_db, raven_client, redis_client, stats_client):
        self.sources = []
        for name, source in self.source_classes:
            source_instance = source(
                geoip_db=geoip_db,
                raven_client=raven_client,
                redis_client=redis_client,
                stats_client=stats_client,
            )
            self.sources.append((name, source_instance))

    def _search(self, query):
        results = self.result_list()
        for name, source in self.sources:
            if source.should_search(query, results):
                results.add(source.search(query))

        return results.best()

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
        if result is not None:
            return self.format_result(result)


class PositionSearcher(Searcher):
    """
    A PositionSearcher will return a position defined by a latitude,
    a longitude and an accuracy in meters.
    """

    result_list = PositionResultList  #:
    result_type = Position  #:
    source_classes = (
        ('internal', InternalPositionSource),
        ('ocid', OCIDPositionSource),
        ('geoip', GeoIPPositionSource),
        ('fallback', FallbackPositionSource),
    )  #:

    def format_result(self, result):
        return {
            'lat': round(result.lat, DEGREE_DECIMAL_PLACES),
            'lon': round(result.lon, DEGREE_DECIMAL_PLACES),
            'accuracy': round(result.accuracy, DEGREE_DECIMAL_PLACES),
            'fallback': result.fallback,
        }


class RegionSearcher(Searcher):
    """
    A RegionSearcher will return a region name and code.
    """

    result_list = RegionResultList  #:
    result_type = Region  #:
    source_classes = (
        ('internal', InternalRegionSource),
        ('geoip', GeoIPRegionSource),
    )  #:

    def format_result(self, result):
        return {
            'region_code': result.region_code,
            'region_name': result.region_name,
            'fallback': result.fallback,
        }
