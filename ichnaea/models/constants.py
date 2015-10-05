"""
Contains model and schemata specific constants.
"""

import re

import mobile_codes
from six import string_types

from ichnaea.constants import MAX_LAT, MIN_LAT, MAX_LON, MIN_LON  # NOQA

# Symbolic constant used in specs passed to normalization functions.
REQUIRED = object()

MAX_ACCURACY = 1000000.0  #: Accuracy is arbitrarily bounded to (0, 1000km).
MIN_ALTITUDE = -10911.0  #: Challenger Deep, Mariana Trench.
MAX_ALTITUDE = 100000.0  #: Karman Line, edge of space.
#: Combination of max/min altitude.
MAX_ALTITUDE_ACCURACY = abs(MAX_ALTITUDE - MIN_ALTITUDE)

MAX_HEADING = 360.0  #: Full 360 degrees.
MAX_SPEED = 300.0  #: A bit less than speed of sound, in meters per second.

WIFI_TEST_MAC = '01005e901000'
"""
We use a `documentation-only multi-cast address
<http://tools.ietf.org/html/rfc7042#section-2.1.1>`_
as a test mac address and ignore data submissions with it.
"""

INVALID_MAC_REGEX = re.compile('(?!(0{12}|f{12}|%s))' % WIFI_TEST_MAC)
VALID_MAC_REGEX = re.compile('([0-9a-fA-F]{12})')

MIN_WIFI_CHANNEL = 0  #: Minimum accepted WiFi channel.
MAX_WIFI_CHANNEL = 166  #: Maximum accepted WiFi channel.

MIN_WIFI_SIGNAL = -200  #: Minimum accepted WiFi signal strength value.
MAX_WIFI_SIGNAL = -1  #: Maximum accepted WiFi signal strength value.

MIN_MCC = 1  #: Minimum accepted network code.
MAX_MCC = 999  #: Maximum accepted network code.

ALL_VALID_MCCS = (
    [int(country.mcc)
     for country in mobile_codes._countries()
     if isinstance(country.mcc, string_types)] +
    [int(code)
     for country in mobile_codes._countries()
     if isinstance(country.mcc, (tuple, list))
     for code in country.mcc]
)  #: All valid mobile country codes.
ALL_VALID_MCCS = set(
    [mcc for mcc in ALL_VALID_MCCS if MIN_MCC <= mcc <= MAX_MCC])
# exclude Tuvalu, as it isn't in our shapefile
ALL_VALID_MCCS = frozenset(ALL_VALID_MCCS - set([553]))

MIN_MNC = 0  #: Minimum accepted network code.
MAX_MNC = 999  #: Maximum accepted network code.

MIN_LAC = 1  #: Minimum accepted cell area code.
MAX_LAC = 65533  #: Maximum accepted cell area code.

MIN_CID = 1  #: Minimum accepted cell id.
MAX_CID = 2 ** 28 - 1  #: Maximum accepted cell id.
MAX_CID_GSM = 2 ** 16 - 1  #: Maximum accepted GSM cell id.

MIN_PSC = 0  #: Minimum accepted psc.
MAX_PSC = 511  #: Maximum accepted psc.
MAX_PSC_LTE = 503  #: Maximum accepted physical cell id.
