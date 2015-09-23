"""
Contains general constants.
"""

from datetime import timedelta

import genc

ALL_VALID_COUNTRIES = frozenset([rec.alpha2 for rec in genc.REGIONS])
"""
A set of all ISO 3166 alpha2 region codes present in the GENC dataset.
"""

DEGREE_DECIMAL_PLACES = 7
"""
We return position and accuracy values rounded to 7 :term:`decimal degrees`,
mostly to make the resulting JSON look prettier. 1E-7 degrees =~ 1.1cm
at the equator, so clients of our external APIs will see that as our
spatial resolution, though in practice we are always in the multiple
of tens of meters range.
"""

MAX_LAT = 85.051  #: Maximum latitude in :term:`Web Mercator` projection.
MIN_LAT = -85.051  #: Minimum latitude in :term:`Web Mercator` projection.

MAX_LON = 180.0  #: Maximum unrestricted longitude in :term:`WSG84`.
MIN_LON = -180.0  #: Minimum unrestricted longitude in :term:`WSG84`.

# Empirical 95th percentile accuracy of ichnaea's responses,
# from feedback testing of observations as queries.
# These values are related to
# :class:`~ichnaea.api.locate.constants.DataAccuracy`
# and adjustments in one need to be reflected in the other.

WIFI_MIN_ACCURACY = 100.0  #: Minimum accuracy returned for Wifi queries.
CELL_MIN_ACCURACY = 5000.0  #: Minimum accuracy returned for cell queries.
LAC_MIN_ACCURACY = 20000.0  #: Minimum accuracy returned for cell area queries.

GEOIP_CITY_ACCURACY = 50000.0
"""
Accuracy returned for GeoIP city based queries.

50km is pure guesswork but should cover most cities.
"""

GEOIP_COUNTRY_ACCURACY = 5000000.0
"""
Usually a per-country accuracy is calculated. This is the worst case
accuracy returned for GeoIP country based queries, based on data
for Russia:

``geocalc.distance(60.0, 100.0, 41.199278, 27.351944) == 5220613 meters``
"""

TEMPORARY_BLOCKLIST_DURATION = timedelta(days=7)
"""
Time during which each temporary blocklisting (detection of
:term:`station` movement) causes observations to be dropped on the floor.
"""

PERMANENT_BLOCKLIST_THRESHOLD = 6
"""
Number of temporary blocklistings that result in a permanent
blocklisting; in other words, number of times a :term:`station` can
legitimately move to a new location before we permanently give
up trying to figure out its fixed location.
"""
