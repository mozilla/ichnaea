from enum import Enum, IntEnum

MAX_WIFI_CLUSTER_KM = 0.5
"""
Maximum distance between WiFi networks to be considered close enough
to be from one consistent observation.
"""

MIN_WIFIS_IN_QUERY = 2
"""
Minimum number of WiFi networks in a query to allow returning results
based on WiFi information.
"""

MIN_WIFIS_IN_CLUSTER = 2
"""
Minimum number of WiFi networks in a close-by cluster to allow returning
results based on the cluster.
"""

MAX_WIFIS_IN_CLUSTER = 5
"""
Maximum number of WiFi networks used from one combined cluster to form
the aggregate result.
"""


class DataSource(IntEnum):
    """
    Data sources for location information. A smaller integer value
    represents a preferred data source.
    """

    Internal = 1
    OCID = 2
    Fallback = 3
    GeoIP = 4


class DataAccuracy(Enum):
    """
    Describes the possible and actual accuracy class of a location query.

    Instances of this class can be compared based on their value or can
    be compared to int/float values.
    """

    high = 1000.0  #: High accuracy, probably WiFi based.
    medium = 40000.0  #: Medium accuracy, probably cell based.
    low = float('inf')  #: Low accuracy, large cell, cell area or GeoIP.

    def __eq__(self, other):
        if isinstance(other, DataAccuracy):
            return self is other
        if isinstance(other, (int, float)):
            return self.value == float(other)
        return super(DataAccuracy, self).__eq__(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        if isinstance(other, DataAccuracy):
            return self.value < other.value
        if isinstance(other, (int, float)):
            return self.value < float(other)
        return super(DataAccuracy, self).__lt__(other)

    def __le__(self, other):
        return self == other or self < other

    def __gt__(self, other):
        return not self <= other

    def __ge__(self, other):
        return not self < other
