"""Search implementation using a database of Bluetooth networks."""

from collections import defaultdict

from ichnaea.api.locate.constants import (
    MAX_BLUE_CLUSTER_METERS,
    MAX_BLUES_IN_CLUSTER,
    BLUE_MAX_ACCURACY,
    BLUE_MIN_ACCURACY,
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
from ichnaea.api.locate.score import station_score
from ichnaea.geocode import GEOCODER
from ichnaea.models import BlueShard
from ichnaea.models.constants import MIN_BLUE_SIGNAL
from ichnaea import util


class BluePositionMixin(object):
    """
    A BluePositionMixin implements a position search using
    the Bluetooth models and a series of clustering algorithms.
    """

    raven_client = None
    result_list = PositionResultList
    result_type = Position

    def should_search_blue(self, query, results):
        return bool(query.blue)

    def search_blue(self, query):
        results = self.result_list()

        blues = query_macs(query, query.blue, self.raven_client, BlueShard)
        for cluster in cluster_networks(blues, query.blue,
                                        min_radius=BLUE_MIN_ACCURACY,
                                        min_signal=MIN_BLUE_SIGNAL,
                                        max_distance=MAX_BLUE_CLUSTER_METERS):
            result = aggregate_cluster_position(
                cluster, self.result_type, 'blue',
                max_networks=MAX_BLUES_IN_CLUSTER,
                min_accuracy=BLUE_MIN_ACCURACY,
                max_accuracy=BLUE_MAX_ACCURACY,
            )
            results.add(result)

        return results


class BlueRegionMixin(object):
    """
    A BlueRegionMixin implements a region search using our Bluetooth data.
    """

    raven_client = None
    result_list = RegionResultList
    result_type = Region

    def should_search_blue(self, query, results):
        return bool(query.blue)

    def search_blue(self, query):
        results = self.result_list()

        now = util.utcnow()
        regions = defaultdict(int)
        blues = query_macs(query, query.blue, self.raven_client, BlueShard)
        for blue in blues:
            regions[blue.region] += station_score(blue, now)

        for code, score in regions.items():
            region = GEOCODER.region_for_code(code)
            if region:
                results.add(self.result_type(
                    region_code=code,
                    region_name=region.name,
                    accuracy=region.radius,
                    score=score))

        return results
