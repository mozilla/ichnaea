"""
Abstract searcher and concrete country and position searchers each using
multiple providers to satisfy a given query.
"""

from collections import defaultdict, deque

from ichnaea.api.locate.geoip import (
    GeoIPCountryProvider,
    GeoIPPositionProvider,
)
from ichnaea.api.locate.cell import (
    CellAreaPositionProvider,
    CellCountryProvider,
    CellPositionProvider,
    OCIDCellAreaPositionProvider,
    OCIDCellPositionProvider,
)
from ichnaea.api.locate.fallback import FallbackProvider
from ichnaea.api.locate.result import EmptyResult
from ichnaea.api.locate.wifi import WifiPositionProvider
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
    A Searcher will use a collection of Provider classes
    to attempt to satisfy a user's query. It will loop over them
    in the order they are specified and use the most accurate result.

    First we attempt a "zoom-in" from cell-lac, to cell
    to wifi, tightening our estimate each step only so
    long as it doesn't contradict the existing best-estimate.
    """

    provider_classes = ()

    def __init__(self, settings,
                 geoip_db, raven_client, redis_client, stats_client):
        self.all_providers = []
        for provider_group, providers in self.provider_classes:
            for provider in providers:
                provider_settings = settings.get_map(
                    'locate:{provider_group}'.format(
                        provider_group=provider_group), {})
                provider_instance = provider(
                    settings=provider_settings,
                    geoip_db=geoip_db,
                    raven_client=raven_client,
                    redis_client=redis_client,
                    stats_client=stats_client,
                )
                self.all_providers.append((provider_group, provider_instance))

    def _search(self, query):
        best_result = EmptyResult()
        best_provider = None
        all_results = defaultdict(deque)

        for provider_group, provider in self.all_providers:
            if provider.should_search(query, best_result):
                provider_result = provider.search(query)
                all_results[provider_group].appendleft(
                    (provider, provider_result))

                if provider_result.more_accurate(best_result):
                    # If this result is more accurate than our previous one,
                    # we'll use it.
                    best_result = provider_result
                    best_provider = provider

                if best_result.accurate_enough():
                    # Stop the loop, if we have a good quality result.
                    break

        if not best_result.found():
            query.stat_count('miss')
        else:
            best_provider.log_hit(query)

        # Log a hit/miss metric for the first data source for
        # which the user provided sufficient data.
        # We check each provider group in reverse order
        # (most accurate to least).
        for provider_group, providers in reversed(self.provider_classes):
            group_results = all_results[provider_group]
            if any([res.query_data for (prov, res) in group_results]):
                # Claim a success if at least one result for a logging
                # group was a success.
                first_provider, first_result = group_results[0]
                found_provider = None
                for (provider, result) in group_results:
                    if result.found():
                        found_provider = provider
                        break
                if found_provider:
                    found_provider.log_success(query)
                else:
                    first_provider.log_failure(query)
                break

        return best_result

    def _prepare(self, result):  # pragma: no cover
        raise NotImplementedError()

    def search(self, query):
        """Provide a type specific query result or return None.

        :param query: A query.
        :type query: :class:`~ichnaea.api.locate.query.Query`
        """
        query.emit_query_stats()
        result = self._search(query)
        if result.found():
            return self._prepare(result)


class PositionSearcher(Searcher):
    """
    A PositionSearcher will return a position defined by a latitude,
    a longitude and an accuracy in meters.
    """

    provider_classes = (
        ('geoip', (
            GeoIPPositionProvider,
        )),
        ('cell', (
            OCIDCellAreaPositionProvider,
            CellAreaPositionProvider,
            OCIDCellPositionProvider,
            CellPositionProvider,
        )),
        ('wifi', (
            WifiPositionProvider,
        )),
        ('fallback', (
            FallbackProvider,
        )),
    )

    def _prepare(self, result):
        return {
            'lat': round(result.lat, DEGREE_DECIMAL_PLACES),
            'lon': round(result.lon, DEGREE_DECIMAL_PLACES),
            'accuracy': round(result.accuracy, DEGREE_DECIMAL_PLACES),
            'fallback': result.fallback,
        }


class CountrySearcher(Searcher):
    """
    A CountrySearcher will return a country name and code.
    """

    provider_classes = (
        ('cell', (CellCountryProvider,)),
        ('geoip', (GeoIPCountryProvider,)),
    )

    def _prepare(self, result):
        return {
            'country_code': result.country_code,
            'country_name': result.country_name,
            'fallback': result.fallback,
        }
