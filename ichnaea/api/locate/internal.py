"""Implementation of a search source based on our internal data."""

import mobile_codes

from ichnaea.api.locate.cell import (
    CellAreaPositionProvider,
    CellPositionProvider,
)
from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.source import (
    CountrySource,
    PositionSource,
)
from ichnaea.api.locate.wifi import WifiPositionMixin


class InternalCountrySource(CountrySource):
    """A country source based on our own crowd-sourced internal data."""

    source = DataSource.internal  #:

    def search(self, query):
        result = self.result_type()

        codes = set()
        for cell in list(query.cell) + list(query.cell_area):
            codes.add(cell.mcc)

        countries = []
        for code in codes:
            countries.extend(mobile_codes.mcc(str(code)))

        if countries:
            if len(countries) == 1:
                # refuse to guess country if there are multiple choices
                result = self.result_type(
                    country_code=countries[0].alpha2,
                    country_name=countries[0].name)

            query.emit_source_stats(self.source, result)

        return result


class InternalPositionSource(PositionSource, WifiPositionMixin):
    """A position source based on our own crowd-sourced internal data."""

    source = DataSource.internal  #:
    providers = ()  #:
    provider_classes = (
        CellAreaPositionProvider,
        CellPositionProvider,
    )  #:

    def __init__(self, settings,
                 geoip_db, raven_client, redis_client, stats_client):
        super(InternalPositionSource, self).__init__(
            settings, geoip_db, raven_client, redis_client, stats_client)
        self.providers = []
        for klass in self.provider_classes:
            self.providers.append(self._init_provider(klass))

    def _init_provider(self, klass):
        return klass(
            settings=self.settings,
            geoip_db=self.geoip_db,
            raven_client=self.raven_client,
            redis_client=self.redis_client,
            stats_client=self.stats_client,
        )

    def search(self, query):
        result = self.result_type()
        source_used = False

        for provider in self.providers:
            if provider.should_search(query, result):
                source_used = True
                provider_result = provider.search(query)

                if provider_result.more_accurate(result):
                    result = provider_result

                if result.accurate_enough():  # pragma: no cover
                    break

        wifi_result = self.search_wifi(query)
        if wifi_result.more_accurate(result):
            result = wifi_result

        if source_used:
            # only emit metrics if at least one of the providers
            # for this source was used
            query.emit_source_stats(self.source, result)

        return result
