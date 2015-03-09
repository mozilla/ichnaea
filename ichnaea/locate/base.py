from collections import namedtuple
from enum import IntEnum

from ichnaea.geocalc import distance
from ichnaea.logging import get_raven_client,     get_stats_client

# parameters for wifi clustering
MAX_WIFI_CLUSTER_KM = 0.5
MIN_WIFIS_IN_QUERY = 2
MIN_WIFIS_IN_CLUSTER = 2
MAX_WIFIS_IN_CLUSTER = 5

# helper class used in searching
Network = namedtuple('Network', ['key', 'lat', 'lon', 'range'])


# Data sources for location information
class DataSource(IntEnum):
    Internal = 1
    OCID = 2
    GeoIP = 3


def estimate_accuracy(lat, lon, points, minimum):
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
