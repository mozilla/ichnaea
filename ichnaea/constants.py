"""
Contains general constants.
"""

from datetime import timedelta

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
