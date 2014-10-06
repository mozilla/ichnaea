from datetime import timedelta
import re

# We return position and accuracy values rounded to 7 decimal places,
# mostly to make the resulting JSON look prettier.  1E-7 degrees =~ 1.1cm
# at the equator, so clients of our external APIs will see that as our
# spatial resolution.
DEGREE_DECIMAL_PLACES = 7

# Restrict latitudes to Web Mercator projection
MAX_LAT = 85.051
MIN_LAT = -85.051

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

# Empirical 95th percentile accuracy of ichnaea's responses,
# from feedback testing of measurements as queries.
WIFI_MIN_ACCURACY = 100
CELL_MIN_ACCURACY = 5000
LAC_MIN_ACCURACY = 20000

# Pure guesswork, "size of a city"
GEOIP_CITY_ACCURACY = 50000
# Worst case scenario for Russia, rounded down a bit
# geocalc.distance(60.0, 100.0, 41.199278, 27.351944) == 5220613 meters
GEOIP_COUNTRY_ACCURACY = 5000000

# We use a documentation-only multi-cast address as a test key
# http://tools.ietf.org/html/rfc7042#section-2.1.1
WIFI_TEST_KEY = "01005e901000"
INVALID_WIFI_REGEX = re.compile("(?!(0{12}|f{12}|%s))" % WIFI_TEST_KEY)
VALID_WIFI_REGEX = re.compile("([0-9a-fA-F]{12})")

# Time during which each temporary blacklisting (detection of station
# movement) causes measurements to be dropped on the floor.
TEMPORARY_BLACKLIST_DURATION = timedelta(days=7)

# Number of temporary blacklistings that result in a permanent
# blacklisting; in other words, number of times a station can
# "legitimately" move to a new location before we permanently give
# up trying to figure out its fixed location.
PERMANENT_BLACKLIST_THRESHOLD = 6
