"""
Contains general constants.
"""

from datetime import timedelta

DEGREE_DECIMAL_PLACES = 7
"""
We return position and accuracy values rounded to 7 decimal places,
mostly to make the resulting JSON look prettier. 1E-7 degrees =~ 1.1cm
at the equator, so clients of our external APIs will see that as our
spatial resolution, though in practice we are always in the multiple
of tens of meters range.
"""

MAX_LAT = 85.051  #: Maximum latitude in Web Mercator projection.
MIN_LAT = -85.051  #: Minimum latitude in Web Mercator projection.

MAX_LON = 180.0  #: Maximum unrestricted longitude.
MIN_LON = -180.0  #: Minimum unrestricted longitude.

# Empirical 95th percentile accuracy of ichnaea's responses,
# from feedback testing of observations as queries.
# These values are related to
# :class:`~ichnaea.api.locate.constants.DataAccuracy`
# and adjustments in one need to be reflected in the other.

WIFI_MIN_ACCURACY = 100  #: Minimum accuracy returned for Wifi queries.
CELL_MIN_ACCURACY = 5000  #: Minimum accuracy returned for cell queries.
LAC_MIN_ACCURACY = 20000  #: Minimum accuracy returned for cell area queries.

GEOIP_CITY_ACCURACY = 50000
"""
Accuracy returned for GeoIP city based queries.

50km is pure guesswork but should cover most cities.
"""

GEOIP_COUNTRY_ACCURACY = 5000000
"""
Usually a per-country accuracy is calculated. This is the worst case
accuracy returned for GeoIP country based queries, based on data
for Russia:

``geocalc.distance(60.0, 100.0, 41.199278, 27.351944) == 5220613 meters``
"""

TEMPORARY_BLACKLIST_DURATION = timedelta(days=7)
"""
Time during which each temporary blacklisting (detection of station
movement) causes observations to be dropped on the floor.
"""

PERMANENT_BLACKLIST_THRESHOLD = 6
"""
Number of temporary blacklistings that result in a permanent
blacklisting; in other words, number of times a station can
legitimately move to a new location before we permanently give
up trying to figure out its fixed location.
"""
