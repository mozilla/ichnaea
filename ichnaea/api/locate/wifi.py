"""Search implementation using a database of WiFi networks."""

from collections import defaultdict

from ichnaea.api.locate.constants import (
    MAX_WIFI_CLUSTER_METERS,
    MAX_WIFIS_IN_CLUSTER,
    WIFI_MAX_ACCURACY,
    WIFI_MIN_ACCURACY,
)
from ichnaea.api.locate.mac import (
    aggregate_cluster_position,
    cluster_networks,
    query_macs,
)
from ichnaea.api.locate.result import (
    Position,
    PositionResultList,
    Region,
    RegionResultList,
)
from ichnaea.geocode import GEOCODER
from ichnaea.models import WifiShard
from ichnaea.models.constants import MIN_WIFI_SIGNAL
from ichnaea import util


class WifiPositionMixin(object):
    """
    A WifiPositionMixin implements a position search using
    the WiFi models and a series of clustering algorithms.
    """

    raven_client = None
    result_list = PositionResultList
    result_type = Position

    def should_search_wifi(self, query, results):
        return bool(query.wifi)

    def search_wifi(self, query):
        results = self.result_list()

        wifis = query_macs(query, query.wifi, self.raven_client, WifiShard)
        for cluster in cluster_networks(wifis, query.wifi,
                                        min_signal=MIN_WIFI_SIGNAL,
                                        max_distance=MAX_WIFI_CLUSTER_METERS):
            results.add(aggregate_cluster_position(
                cluster, self.result_type,
                max_networks=MAX_WIFIS_IN_CLUSTER,
                min_accuracy=WIFI_MIN_ACCURACY,
                max_accuracy=WIFI_MAX_ACCURACY,
            ))

        return results


class WifiRegionMixin(object):
    """
    A WifiRegionMixin implements a region search using our wifi data.
    """

    raven_client = None
    result_list = RegionResultList
    result_type = Region

    def should_search_wifi(self, query, results):
        return bool(query.wifi)

    def search_wifi(self, query):
        results = self.result_list()

        now = util.utcnow()
        regions = defaultdict(int)
        wifis = query_macs(query, query.wifi, self.raven_client, WifiShard)
        for wifi in wifis:
            regions[wifi.region] += wifi.score(now)

        for code, score in regions.items():
            region = GEOCODER.region_for_code(code)
            if region:
                results.add(self.result_type(
                    region_code=code,
                    region_name=region.name,
                    accuracy=region.radius,
                    score=score))

        return results
