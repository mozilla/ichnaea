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
