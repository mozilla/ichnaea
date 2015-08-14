"""
Abstract searcher and concrete country and position searchers each using
multiple sources to satisfy a given query.
"""

from collections import defaultdict

from ichnaea.api.locate.fallback import FallbackPositionSource
from ichnaea.api.locate.geoip import (
    GeoIPCountrySource,
    GeoIPPositionSource,
)
from ichnaea.api.locate.internal import (
    InternalCountrySource,
    InternalPositionSource,
)
from ichnaea.api.locate.ocid import OCIDPositionSource
from ichnaea.api.locate.result import (
    Country,
    Position,
    ResultList,
)
from ichnaea.constants import DEGREE_DECIMAL_PLACES


def _configure_searcher(klass, settings, geoip_db=None, raven_client=None,
                        redis_client=None, stats_client=None, _searcher=None):
    if _searcher is not None:
        return _searcher
    return klass(settings, geoip_db, raven_client, redis_client, stats_client)


def configure_country_searcher(settings, geoip_db=None, raven_client=None,
                               redis_client=None, stats_client=None,
                               _searcher=None):
    """
    Configure and return a configured
    :class:`~ichnaea.api.locate.searcher.CountrySearcher` instance.

    :param _searcher: Test-only hook to provide a pre-configured searcher.
    """
    return _configure_searcher(
        CountrySearcher, settings, geoip_db=geoip_db,
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

    def _best_result(self, results):
        raise NotImplementedError()

    def _search(self, query):
        results = ResultList(result=self.result_type())
        for name, source in self.sources:
            if source.should_search(query, results):
                results.add(source.search(query))

        return self._best_result(results)

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

    def _best_result(self, results):
        return results.best()


class CountrySearcher(Searcher):
    """
    A CountrySearcher will return a country name and code.
    """

    result_type = Country
    source_classes = (
        ('internal', InternalCountrySource),
        ('geoip', GeoIPCountrySource),
    )

    def format_result(self, result):
        return {
            'country_code': result.country_code,
            'country_name': result.country_name,
            'fallback': result.fallback,
        }

    def _best_result(self, results):
        found = [res for res in results if not res.empty()]
        if len(results) == 1 or len(found) == 0:
            return results[0]

        if len(found) == 1:
            return found[0]

        # group by country code
        grouped = defaultdict(list)
        for result in found:
            grouped[result.country_code].append(result)

        countries = []
        for code, values in grouped.items():
            country = grouped[code][0]
            countries.append(
                (len(values), country.accuracy, country))

        # pick the country with the most entries,
        # break tie by country with the largest radius
        countries = sorted(countries, reverse=True)

        return countries[0][2]
