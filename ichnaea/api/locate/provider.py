"""
Base implementation of a location provider.
"""

from collections import namedtuple
from functools import partial

from ichnaea.api.locate.constants import DataSource
from ichnaea.geocalc import distance

# helper class used in searching
Network = namedtuple('Network', ['key', 'lat', 'lon', 'range'])


class Provider(object):
    """
    A Provider provides an interface for a class
    which will provide a location given a set of query data.

    .. attribute:: log_name

        The name to use in logging statements, for example 'cell_lac'
    """

    fallback_field = None
    log_name = None
    location_type = None
    source = DataSource.Internal

    def __init__(self, settings,
                 geoip_db, raven_client, redis_client, stats_client):
        self.settings = settings
        self.geoip_db = geoip_db
        self.raven_client = raven_client
        self.redis_client = redis_client
        self.stats_client = stats_client
        self.location_type = partial(
            self.location_type,
            source=self.source,
            fallback=self.fallback_field,
        )

    def should_locate(self, query, location):
        """
        Given a location query and a possible location
        found by another provider, check if this provider should
        attempt to perform a location search.

        :param query: A location query.
        :type query: :class:`~ichnaea.api.locate.query.Query`

        :rtype: bool
        """
        if self.fallback_field is not None:
            return bool(getattr(query.fallback, self.fallback_field, True))

        return True

    def locate(self, query):  # pragma: no cover
        """
        Provide a location given the provided query.

        :param query: A location query.
        :type query: :class:`~ichnaea.api.locate.query.Query`

        :rtype: :class:`~ichnaea.api.locate.location.Location`
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
            # this one takes the maximum distance from location
            # to any of the provided points.
            accuracy = max([distance(lat, lon, p.lat, p.lon) * 1000
                            for p in points])
        if accuracy is not None:
            accuracy = float(accuracy)
        return max(accuracy, minimum)

    def log_hit(self, query):
        """Log a stat metric for a successful provider lookup."""
        query.stat_count('{metric}_hit'.format(metric=self.log_name))

    def log_success(self, query):
        """
        Log a stat metric for a request in which the user provided
        relevant data for this provider and the lookup was successful.
        """
        if query.api_key.log:
            query.stat_count('api_log.{key}.{metric}_hit'.format(
                key=query.api_key.name, metric=self.log_name))

    def log_failure(self, query):
        """
        Log a stat metric for a request in which the user provided
        relevant data for this provider and the lookup failed.
        """
        if query.api_key.log:
            query.stat_count('api_log.{key}.{metric}_miss'.format(
                key=query.api_key.name, metric=self.log_name))
