from enum import Enum, IntEnum

_MAX_INT = 2 ** 32 - 1

EARTH_CIRCUMFERENCE = 40000000.0
"""
Approximate circumference of the Earth in meters.
"""

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

    internal = 1
    ocid = 2
    fallback = 3
    geoip = 4


class DataAccuracy(Enum):
    """
    Describes the possible and actual accuracy class of a locate query.

    Instances of this class can be compared based on their value or can
    be compared to int/float values.

    These values are related to :data:`~ichnaea.constants.CELL_MIN_ACCURACY`
    and :data:`~ichnaea.constants.GEOIP_CITY_ACCURACY` and adjustments
    in one need to be reflected in the other.
    """

    high = 1000.0  #: High accuracy, probably WiFi based.
    medium = 40000.0  #: Medium accuracy, probably cell based.
    low = EARTH_CIRCUMFERENCE  #: Low accuracy, large cell, cell area or GeoIP.
    none = float('inf')  # No accuracy at all.

    @classmethod
    def from_number(cls, num):
        """
        Return a specific DataAccuracy enum value based on a float/int
        argument.
        """
        num = float(num)
        if num <= cls.high.value:
            return cls.high
        elif num <= cls.medium.value:
            return cls.medium
        elif num <= cls.low.value:
            return cls.low
        return cls.none

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

    def __hash__(self):
        if self is DataAccuracy.none:
            # a value different from all other ones
            return _MAX_INT
        return int(self.value)
