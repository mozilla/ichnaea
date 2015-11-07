from enum import Enum

_MAX_INT = 2 ** 32 - 1

EARTH_CIRCUMFERENCE = 40000000.0
"""
Approximate circumference of the Earth in meters.
"""

MAX_WIFI_CLUSTER_METERS = 1000.0
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

MAX_WIFIS_IN_CLUSTER = 10
"""
Maximum number of WiFi networks used from one combined cluster to form
the aggregate result.
"""

# These values are related to
# :class:`~ichnaea.api.locate.constants.DataAccuracy`
# and adjustments in one need to be reflected in the other.

WIFI_MIN_ACCURACY = 100.0  #: Minimum accuracy returned for Wifi queries.
WIFI_MAX_ACCURACY = 1000.0  # Maximum accuracy returned for Wifi queries.

CELL_MIN_ACCURACY = 1000.1  #: Minimum accuracy returned for cell queries.
CELL_MAX_ACCURACY = 50000.0  #: Maximum accuracy returned for cell queries.
CELLAREA_MIN_ACCURACY = 50000.1  #: Minimum accuracy for cell area queries.
CELLAREA_MAX_ACCURACY = 500000.0  #: Maximum accuracy for cell area queries.


class DataSource(Enum):
    """
    Data sources for location information. The names are used in metrics.
    """

    internal = 1  #: Internal crowd-sourced data.
    ocid = 2  #: Data from :term:`OCID` project.
    fallback = 3  #: Data from external fallback web service.
    geoip = 4  #: GeoIP database.


class DataAccuracy(Enum):
    """
    Describes the possible and actual accuracy class of a locate query.

    Instances of this class can be compared based on their value or can
    be compared to int/float values.

    These values are related to :data:`~ichnaea.constants.CELL_MIN_ACCURACY`
    and :data:`~ichnaea.geoip.CITY_RADIUS` and adjustments
    in one need to be reflected in the other.
    """

    high = 1000.0  #: High accuracy, probably WiFi based.
    medium = 50000.0  #: Medium accuracy, probably cell based.
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
