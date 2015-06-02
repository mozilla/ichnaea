from collections import defaultdict, deque

from ichnaea.locate.location import EmptyLocation
from ichnaea.locate.provider import (
    CellAreaPositionProvider,
    CellCountryProvider,
    CellPositionProvider,
    FallbackProvider,
    GeoIPCountryProvider,
    GeoIPPositionProvider,
    OCIDCellAreaPositionProvider,
    OCIDCellPositionProvider,
    WifiPositionProvider,
)
from ichnaea.locate.stats import StatsLogger


class Searcher(StatsLogger):
    """
    A Searcher will use a collection of Provider classes
    to attempt to identify a user's location. It will loop over them
    in the order they are specified and use the most accurate location.
    """
    # First we attempt a "zoom-in" from cell-lac, to cell
    # to wifi, tightening our estimate each step only so
    # long as it doesn't contradict the existing best-estimate.

    provider_classes = ()

    def __init__(self, session_db, geoip_db,
                 redis_client, settings, *args, **kwargs):
        super(Searcher, self).__init__(*args, **kwargs)

        self.all_providers = []
        for provider_group, providers in self.provider_classes:
            for provider in providers:
                provider_settings = settings.get(
                    'locate:{provider_group}'.format(
                        provider_group=provider_group), {})
                provider_instance = provider(
                    session_db=session_db,
                    geoip_db=geoip_db,
                    redis_client=redis_client,
                    settings=provider_settings,
                    api_key=self.api_key,
                    api_name=self.api_name,
                )
                self.all_providers.append((provider_group, provider_instance))

    def _search(self, data):
        best_location = EmptyLocation()
        best_location_provider = None
        all_locations = defaultdict(deque)

        for provider_group, provider in self.all_providers:
            if provider.should_locate(data, best_location):
                provider_location = provider.locate(data)
                all_locations[provider_group].appendleft(
                    (provider, provider_location))

                if provider_location.more_accurate(best_location):
                    # If this location is more accurate than our previous one,
                    # we'll use it.
                    best_location = provider_location
                    best_location_provider = provider

                if best_location.accurate_enough():
                    # Stop the loop, if we have a good quality location.
                    break

        if not best_location.found():
            self.stat_count('miss')
        else:
            best_location_provider.log_hit()

        # Log a hit/miss metric for the first data source for
        # which the user provided sufficient data.
        # We check each provider group in reverse order
        # (most accurate to least).
        for provider_group, providers in reversed(self.provider_classes):
            group_locations = all_locations[provider_group]
            if any([l.query_data for (p, l) in group_locations]):
                # Claim a success if at least one location for a logging
                # group was a success.
                first_provider, first_location = group_locations[0]
                found_provider = None
                for (provider, location) in group_locations:
                    if location.found():
                        found_provider = provider
                        break
                if found_provider:
                    found_provider.log_success()
                else:
                    first_provider.log_failure()
                break

        return best_location

    def _prepare(self, location):  # pragma: no cover
        raise NotImplementedError()

    def search(self, data):
        """Provide a type specific search location or return None."""
        location = self._search(data)
        if location.found():
            return self._prepare(location)


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

    def _prepare(self, location):
        return {
            'lat': location.lat,
            'lon': location.lon,
            'accuracy': location.accuracy,
            'fallback': location.fallback,
        }


class CountrySearcher(Searcher):
    """
    A CountrySearcher will return a country name and code.
    """

    provider_classes = (
        ('cell', (CellCountryProvider,)),
        ('geoip', (GeoIPCountryProvider,)),
    )

    def _prepare(self, location):
        return {
            'country_name': location.country_name,
            'country_code': location.country_code,
        }
