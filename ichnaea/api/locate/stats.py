"""
Helper class for providing detailed query statistics.
"""

from ichnaea.log import (
    get_raven_client,
    get_stats_client,
)


class StatsLogger(object):

    def __init__(self, api_key, api_name):
        """
        A StatsLogger sends counted and timed named statistics to
        a statistic aggregator client.

        :param api_key: An ApiKey instance for the calling user
        :type api_key: ApiKey
        :param api_name: Name of the API, used as stats prefix
            (for example 'geolocate')
        :type api_name: str
        """
        self.api_key = api_key
        self.api_name = api_name
        self.raven_client = get_raven_client()
        self.stats_client = get_stats_client()

    def stat_count(self, stat):
        self.stats_client.incr('{api}.{stat}'.format(
            api=self.api_name, stat=stat))

    def stat_timer(self, stat):
        return self.stats_client.timer('{api}.{stat}'.format(
            api=self.api_name, stat=stat))
