from ichnaea.api.locate.cell import (
    OCIDCellAreaPositionProvider,
    OCIDCellPositionProvider,
)
from ichnaea.api.locate.constants import DataSource
from ichnaea.api.locate.source import PositionSource


class OCIDPositionSource(PositionSource):

    fallback_field = None  #:
    source = DataSource.ocid  #:
    providers = ()  #:
    provider_classes = (
        OCIDCellAreaPositionProvider,
        OCIDCellPositionProvider,
    )  #:

    def __init__(self, settings,
                 geoip_db, raven_client, redis_client, stats_client):
        super(OCIDPositionSource, self).__init__(
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

        if source_used:
            # only emit metrics if at least one of the providers
            # for this source was used
            query.emit_source_stats(self.source, result)

        return result
