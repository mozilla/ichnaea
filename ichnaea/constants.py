from datetime import timedelta

# We return position and accuracy values rounded to 7 decimal places,
# mostly to make the resulting JSON look prettier.  1E-7 degrees =~ 1.1cm
# at the equator, so clients of our external APIs will see that as our
# spatial resolution.
DEGREE_DECIMAL_PLACES = 7

MAX_LAT = 85.051  #: Maximum latitude in Web Mercator projection.
MIN_LAT = -85.051  #: Minimum latitude in Web Mercator projection.

MAX_LON = 180.0  #: Maximum unrestricted longitude.
MIN_LON = -180.0  #: Minimum unrestricted longitude.

# Empirical 95th percentile accuracy of ichnaea's responses,
# from feedback testing of observations as queries.
WIFI_MIN_ACCURACY = 100
CELL_MIN_ACCURACY = 5000
LAC_MIN_ACCURACY = 20000

# Pure guesswork, size of a city
GEOIP_CITY_ACCURACY = 50000
# Worst case scenario for Russia, rounded down a bit
# geocalc.distance(60.0, 100.0, 41.199278, 27.351944) == 5220613 meters
GEOIP_COUNTRY_ACCURACY = 5000000

# Time during which each temporary blacklisting (detection of station
# movement) causes observations to be dropped on the floor.
TEMPORARY_BLACKLIST_DURATION = timedelta(days=7)

# Number of temporary blacklistings that result in a permanent
# blacklisting; in other words, number of times a station can
# legitimately move to a new location before we permanently give
# up trying to figure out its fixed location.
PERMANENT_BLACKLIST_THRESHOLD = 6
