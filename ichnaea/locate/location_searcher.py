from collections import defaultdict, deque

from ichnaea.locate.location import EmptyLocation
from ichnaea.locate.location_provider import (
    PositionGeoIPLocationProvider,
    OCIDCellAreaLocationProvider,
    CellAreaLocationProvider,
    OCIDCellLocationProvider,
    CellLocationProvider,
    WifiLocationProvider,
    CellCountryProvider,
    CountryGeoIPLocationProvider,
)
from ichnaea.stats import StatsLogger


class LocationSearcher(StatsLogger):
    """
    An LocationSearcher will use a collection of LocationProvider
    classes to attempt to identify a user's location. It will loop over them
    in the order they are specified and use the most accurate location.
    """
    # First we attempt a "zoom-in" from cell-lac, to cell
    # to wifi, tightening our estimate each step only so
    # long as it doesn't contradict the existing best-estimate.

    provider_classes = ()

    def __init__(self, session_db, geoip_db, *args, **kwargs):
        super(LocationSearcher, self).__init__(*args, **kwargs)

        self.all_providers = []
        for provider_group, providers in self.provider_classes:
            for provider in providers:
                provider_instance = provider(
                    session_db=session_db,
                    geoip_db=geoip_db,
                    api_key_log=self.api_key_log,
                    api_key_name=self.api_key_name,
                    api_name=self.api_name,
                )
                self.all_providers.append((provider_group, provider_instance))

    def search_location(self, data):
        best_location = EmptyLocation()
        best_location_provider = None
        all_locations = defaultdict(deque)

        for provider_group, provider in self.all_providers:
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

    def prepare_location(self, location):  # pragma: no cover
        raise NotImplementedError()

    def search(self, data):
        """Provide a type specific search location or return None."""
        location = self.search_location(data)
        if location.found():
            return self.prepare_location(location)
        return None


class PositionSearcher(LocationSearcher):
    """
    A PositionSearcher will return a position defined by a latitude,
    a longitude and an accuracy in meters.
    """

    provider_classes = (
        ('geoip', (
            PositionGeoIPLocationProvider,
        )),
        ('cell', (
            OCIDCellAreaLocationProvider,
            CellAreaLocationProvider,
            OCIDCellLocationProvider,
            CellLocationProvider,
        )),
        ('wifi', (
            WifiLocationProvider,
        )),
    )

    def prepare_location(self, location):
        return {
            'lat': location.lat,
            'lon': location.lon,
            'accuracy': location.accuracy,
        }


class CountrySearcher(LocationSearcher):
    """
    A CountrySearcher will return a country name and code.
    """

    provider_classes = (
        ('cell', (CellCountryProvider,)),
        ('geoip', (CountryGeoIPLocationProvider,)),
    )

    def prepare_location(self, location):
        return {
            'country_name': location.country_name,
            'country_code': location.country_code,
        }
