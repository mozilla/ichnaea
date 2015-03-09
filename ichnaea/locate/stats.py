from collections import namedtuple
from enum import IntEnum

from ichnaea.geocalc import distance
from ichnaea.logging import get_raven_client,     get_stats_client


class StatsLogger(object):

    def __init__(self, api_key_name, api_key_log, api_name):
        """
        A StatsLogger sends counted and timed named statistics to
        a statistic aggregator client.

        :param api_key_name: Human readable API key name
            (for example 'test_1')
        :type api_key_name: str
        :param api_key_log: Gather additional API key specific stats?
        :type api_key_log: bool
        :param api_name: Name of the API, used as stats prefix
            (for example 'geolocate')
        :type api_name: str
        """
        self.api_key_name = api_key_name
        self.api_key_log = api_key_log
        self.api_name = api_name
        self.raven_client = get_raven_client()
        self.stats_client = get_stats_client()

    def stat_count(self, stat):
        self.stats_client.incr('{api}.{stat}'.format(
            api=self.api_name, stat=stat))

    def stat_time(self, stat, count):
        self.stats_client.timing('{api}.{stat}'.format(
            api=self.api_name, stat=stat), count)
