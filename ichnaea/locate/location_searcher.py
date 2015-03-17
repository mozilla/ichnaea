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


def map_data(data, client_addr=None):
    """
    Transform a geolocate API dictionary to an equivalent search API
    dictionary.
    """
    mapped = {
        'geoip': None,
        'radio': data.get('radioType', None),
        'cell': [],
        'wifi': [],
    }
    if client_addr:
        mapped['geoip'] = client_addr

    if not data:
        return mapped

    if 'cellTowers' in data:
        for cell in data['cellTowers']:
            new_cell = {
                'mcc': cell['mobileCountryCode'],
                'mnc': cell['mobileNetworkCode'],
                'lac': cell['locationAreaCode'],
                'cid': cell['cellId'],
            }
            # If a radio field is populated in any one of the cells in
            # cellTowers, this is a buggy geolocate call from FirefoxOS.
            # Just pass on the radio field, as long as it's non-empty.
            if 'radio' in cell and cell['radio'] != '':
                new_cell['radio'] = cell['radio']
            mapped['cell'].append(new_cell)

    if 'wifiAccessPoints' in data:
        mapped['wifi'] = [{
            'key': wifi['macAddress'],
        } for wifi in data['wifiAccessPoints']]

    return mapped


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
    log_groups = ('wifi', 'cell', 'geoip')

    def __init__(self, db_sources, *args, **kwargs):
        super(LocationSearcher, self).__init__(*args, **kwargs)

        self.all_providers = [
            cls(
                db_sources[cls.db_source_field],
                api_key_log=self.api_key_log,
                api_key_name=self.api_key_name,
                api_name=self.api_name,
            ) for cls in self.provider_classes]

    def search_location(self, data):
        best_location = EmptyLocation()
        best_location_provider = None
        all_locations = defaultdict(deque)

        for provider in self.all_providers:
            provider_location = provider.locate(data)
            all_locations[provider.log_group].appendleft(
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
        # which the user provided sufficient data
        for log_group in self.log_groups:
            group_locations = all_locations[log_group]
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
        PositionGeoIPLocationProvider,
        OCIDCellAreaLocationProvider,
        CellAreaLocationProvider,
        OCIDCellLocationProvider,
        CellLocationProvider,
        WifiLocationProvider,
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
        CellCountryProvider,
        CountryGeoIPLocationProvider,
    )

    def prepare_location(self, location):
        return {
            'country_name': location.country_name,
            'country_code': location.country_code,
        }
