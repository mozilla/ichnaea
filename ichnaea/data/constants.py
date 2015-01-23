import re

import mobile_codes


# Symbolic constant used in specs passed to normalization functions.
REQUIRED = object()

MAX_LAT = 85.051  #: Maximum latitude in Web Mercator projection.
MIN_LAT = -85.051  #: Minimum latitude in Web Mercator projection.

MAX_LON = 180.0  #: Maximum unrestricted longitude.
MIN_LON = -180.0  #: Minimum unrestricted longitude.

# Accuracy on land is arbitrarily bounded to [0, 1000km],
# past which it seems more likely we're looking at bad data.
MAX_ACCURACY = 1000000

# Challenger Deep, Mariana Trench.
MIN_ALTITUDE = -10911

# Karman Line, edge of space.
MAX_ALTITUDE = 100000

MAX_ALTITUDE_ACCURACY = abs(MAX_ALTITUDE - MIN_ALTITUDE)

MAX_HEADING = 360.0

# A bit less than speed of sound, in meters per second
MAX_SPEED = 300.0

ALL_VALID_MCCS = frozenset(
    [int(country.mcc)
     for country in mobile_codes._countries()
     if isinstance(country.mcc, basestring)] +
    [int(code)
     for country in mobile_codes._countries()
     if isinstance(country.mcc, (tuple, list))
     for code in country.mcc]
)

# We use a documentation-only multi-cast address as a test key
# http://tools.ietf.org/html/rfc7042#section-2.1.1
WIFI_TEST_KEY = '01005e901000'
INVALID_WIFI_REGEX = re.compile('(?!(0{12}|f{12}|%s))' % WIFI_TEST_KEY)
VALID_WIFI_REGEX = re.compile('([0-9a-fA-F]{12})')

MIN_WIFI_CHANNEL = 0
MAX_WIFI_CHANNEL = 166

MIN_WIFI_SIGNAL = -200
MAX_WIFI_SIGNAL = -1

MAX_ALL_CID = 2 ** 32 - 1
MAX_CDMA_CID = 2 ** 16 - 1
MAX_LTE_CID = 2 ** 28 - 1
MAX_LAC = 2 ** 16 - 1
