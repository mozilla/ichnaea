"""Base implementation of a search source."""

from functools import partial

from ichnaea.api.locate.result import (
    Country,
    Position,
)


class Source(object):
    """
    A source represents data from the same data source or
    collection effort, for example a GeoIP database or our own
    crowd-sourced data collection.
    """

    fallback_field = None  #:
    result_type = None  #:
    source = None  #:

    def __init__(self, settings,
                 geoip_db, raven_client, redis_client, stats_client):
        self.settings = settings
        self.geoip_db = geoip_db
        self.raven_client = raven_client
        self.redis_client = redis_client
        self.stats_client = stats_client
        self.result_type = partial(
            self.result_type,
            source=self.source,
            fallback=self.fallback_field,
        )

    def should_search(self, query, result):
        """
        Given a query and a possible result found by another source,
        check if this source should attempt to perform a search.

        :param query: A query.
        :type query: :class:`~ichnaea.api.locate.query.Query`

        :rtype: bool
        """
        if self.fallback_field is not None:
            return bool(getattr(query.fallback, self.fallback_field, True))

        return True

    def search(self, query):  # pragma: no cover
        """Provide a type specific possibly empty query result.

        :param query: A query.
        :type query: :class:`~ichnaea.api.locate.query.Query`
        """
        raise NotImplementedError()


class CountrySource(Source):
    """
    A CountrySource will return a country result with
    a country name and code in it.
    """

    result_type = Country  #:


class PositionSource(Source):
    """
    A PositionSource will return a position result with
    a latitude, a longitude and an accuracy in meters in it.
    """

    result_type = Position  #:


class PositionMultiSource(Source):
    """A source based on multiple position providers."""

    providers = ()  #:
    provider_classes = ()  #:
    result_type = Position  #:

    def __init__(self, settings,
                 geoip_db, raven_client, redis_client, stats_client):
        super(PositionMultiSource, self).__init__(
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
