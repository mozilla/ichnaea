from enum import IntEnum

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
