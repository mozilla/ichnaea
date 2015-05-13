import re

import mobile_codes

from ichnaea.constants import MAX_LAT, MIN_LAT, MAX_LON, MIN_LON  # NOQA

# Symbolic constant used in specs passed to normalization functions.
REQUIRED = object()

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

MIN_CID = 1
MAX_CID_CDMA = 2 ** 16 - 1
MAX_CID_LTE = 2 ** 28 - 1
MAX_CID_ALL = 2 ** 32 - 1

MIN_LAC = 1
MAX_LAC_GSM_UMTS_LTE = 65533
MAX_LAC_ALL = 65534
