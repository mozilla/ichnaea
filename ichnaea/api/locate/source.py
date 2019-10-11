"""Base implementation of a search source."""

from functools import partial

from ichnaea.api.locate.result import (
    Position,
    PositionResultList,
    Region,
    RegionResultList,
)


class Source(object):
    """
    A source represents data from the same data source or
    collection effort, for example a GeoIP database or our own
    crowd-sourced data collection.
    """

    fallback_field = None
    result_list = None
    result_type = None
    source = None

    def __init__(self, geoip_db, raven_client, redis_client, data_queues):
        self.geoip_db = geoip_db
        self.raven_client = raven_client
        self.redis_client = redis_client
        self.data_queues = data_queues
        self.result_type = partial(
            self.result_type, source=self.source, fallback=self.fallback_field
        )

    def should_search(self, query, results):
        """
        Given a query and possible results found by other sources,
        check if this source should attempt to perform a search.

        :param query: A query.
        :type query: :class:`~ichnaea.api.locate.query.Query`

        :param results: All results found by other sources.
        :type results: :class:`~ichnaea.api.locate.result.ResultList`

        :rtype: bool
        """
        if self.fallback_field is not None:
            return bool(getattr(query.fallback, self.fallback_field, True))

        return True

    def search(self, query):
        """Provide a type specific possibly empty result list.

        :param query: A query.
        :type query: :class:`~ichnaea.api.locate.query.Query`
        """
        raise NotImplementedError()


class PositionSource(Source):
    """
    A PositionSource will return a position result with
    a latitude, a longitude and an accuracy in meters in it.
    """

    result_list = PositionResultList
    result_type = Position


class RegionSource(Source):
    """
    A RegionSource will return a region result with
    a region name and code in it.
    """

    result_list = RegionResultList
    result_type = Region
