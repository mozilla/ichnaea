"""Base implementation of a search provider."""

from collections import namedtuple
from functools import partial

from ichnaea.geocalc import distance

# helper class used in searching
Network = namedtuple('Network', ['key', 'lat', 'lon', 'range'])


class Provider(object):
    """
    A Provider provides an interface for a class,
    which will provide a result given a set of query data.
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
        Given a query and a possible result found by another provider,
        check if this provider should attempt to perform a search.

        :param query: A query.
        :type query: :class:`~ichnaea.api.locate.query.Query`

        :rtype: bool
        """
        if self.fallback_field is not None:
            return bool(getattr(query.fallback, self.fallback_field, True))

        return True

    def search(self, query):  # pragma: no cover
        """
        Provide a result given the provided query.

        :param query: A query.
        :type query: :class:`~ichnaea.api.locate.query.Query`

        :rtype: :class:`~ichnaea.api.locate.result.Result`
        """
        raise NotImplementedError()

    def _estimate_accuracy(self, lat, lon, points, minimum):
        """
        Return the maximum range between a position (lat/lon) and a
        list of secondary positions (points). But at least use the
        specified minimum value.
        """
        if len(points) == 1:
            accuracy = points[0].range
        else:
            # Terrible approximation, but hopefully better
            # than the old approximation, "worst-case range":
            # this one takes the maximum distance from position
            # to any of the provided points.
            accuracy = max([distance(lat, lon, p.lat, p.lon) * 1000
                            for p in points])
        if accuracy is not None:
            accuracy = float(accuracy)
        return max(accuracy, minimum)
