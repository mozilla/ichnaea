import re

import mobile_codes

from ichnaea.customjson import (
    decode_datetime,
    encode_datetime,
)
from ichnaea import geocalc
from ichnaea.models import (
    MAX_RADIO_TYPE,
    MIN_RADIO_TYPE,
    RADIO_TYPE,
)

# Symbolic constant used in specs passed to normalization functions.
REQUIRED = object()

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

ALL_VALID_MCCS = frozenset(
    [int(country.mcc)
     for country in mobile_codes._countries()
     if isinstance(country.mcc, str)] +
    [int(code)
     for country in mobile_codes._countries()
     if isinstance(country.mcc, tuple)
     for code in country.mcc]
)

# We use a documentation-only multi-cast address as a test key
# http://tools.ietf.org/html/rfc7042#section-2.1.1
WIFI_TEST_KEY = "01005e901000"
INVALID_WIFI_REGEX = re.compile("(?!(0{12}|f{12}|%s))" % WIFI_TEST_KEY)
VALID_WIFI_REGEX = re.compile("([0-9a-fA-F]{12})")


def valid_wifi_pattern(key):
    return INVALID_WIFI_REGEX.match(key) and \
        VALID_WIFI_REGEX.match(key) and len(key) == 12


def normalized_wifi_key(key):
    if ":" in key or "-" in key or "." in key:
        key = key.replace(":", "").replace("-", "").replace(".", "")
    return key.lower()


def normalized_dict_value(d, k, lo, hi, default=REQUIRED):
    """
    Returns a dict value d[k] if within range [lo,hi]. If the
    Value is missing or out of range, return default, unless
    default is REQUIRED, in which case return None.
    """
    if k not in d or d[k] < lo or d[k] > hi:
        if default is REQUIRED:
            return None
        else:
            return default
    else:
        return d[k]


def normalized_dict(d, specs):
    """
    Returns a copy of the provided dict, with its values set to a default
    value if missing or outside a specified range. If any missing or
    out-of-range values were specified as REQUIRED, return None.

    Arguments:
    d -- a dict to normalize
    specs -- a dict mapping keys to (lo, hi, default) triples, where
             default may be the symbolic constant REQUIRED;
             if any REQUIRED fields are missing or out of
             range, return None.
    """
    if not isinstance(d, dict):
        return None

    n = {}
    for (k, (lo, hi, default)) in specs.items():
        v = normalized_dict_value(d, k, lo, hi, default)
        if v is None:
            return None
        n[k] = v

    # copy forward anything not specified
    for (k, v) in d.items():
        if k not in n:
            n[k] = v
    return n


def normalized_measure_dict(d):
    """
    Returns a normalized copy of the provided measurement dict d,
    or None if the dict was invalid.
    """
    d = normalized_dict(
        d, dict(lat=(MIN_LAT, MAX_LAT, REQUIRED),
                lon=(-180.0, 180.0, REQUIRED),
                heading=(0.0, MAX_HEADING, -1.0),
                speed=(0, MAX_SPEED, -1.0),
                altitude=(MIN_ALTITUDE, MAX_ALTITUDE, 0),
                altitude_accuracy=(0, MAX_ALTITUDE_ACCURACY, 0),
                accuracy=(0, MAX_ACCURACY, 0)))

    if d is None:
        return None

    if 'time' not in d:
        d['time'] = ''
    d['time'] = encode_datetime(decode_datetime(d['time']))
    return d


def normalized_wifi_channel(d):
    chan = int(d.get('channel', 0))

    if 0 < chan and chan < 166:
        return chan

    # if no explicit channel was given, calculate
    freq = d.get('frequency', 0)

    if 2411 < freq < 2473:
        # 2.4 GHz band
        return (freq - 2407) // 5

    elif 5169 < freq < 5826:
        # 5 GHz band
        return (freq - 5000) // 5

    return 0


def normalized_wifi_dict(d):
    """
    Returns a normalized copy of the provided wifi dict d,
    or None if the dict was invalid.
    """
    d = normalized_dict(
        d, dict(signal=(-200, -1, 0),
                signalToNoiseRatio=(0, 100, 0)))

    if d is None:
        return None

    if 'key' not in d:
        return None

    d['key'] = normalized_wifi_key(d['key'])

    if not valid_wifi_pattern(d['key']):
        return None

    d['channel'] = normalized_wifi_channel(d)
    d.pop('frequency', 0)

    return d


def normalized_wifi_measure_dict(d):
    """
    Returns a normalized copy of the provided wifi-measure dict d,
    or None if the dict was invalid.
    """
    d = normalized_wifi_dict(d)
    return normalized_measure_dict(d)


def normalized_cell_dict(d, default_radio=-1):
    """
    Returns a normalized copy of the provided cell dict d,
    or None if the dict was invalid.
    """
    if not isinstance(d, dict):
        return None

    d = d.copy()
    if 'radio' in d and isinstance(d['radio'], basestring):
        d['radio'] = RADIO_TYPE.get(d['radio'], -1)

    d = normalized_dict(
        d, dict(radio=(MIN_RADIO_TYPE, MAX_RADIO_TYPE, default_radio),
                mcc=(1, 999, REQUIRED),
                mnc=(0, 32767, REQUIRED),
                lac=(1, 65535, -1),
                cid=(1, 268435455, -1),
                psc=(0, 512, -1)))

    if d is None:
        return None

    # Check against the list of all known valid mccs
    if d['mcc'] not in ALL_VALID_MCCS:
        return None

    # If a default radio was set, and we don't know, use it as fallback
    if d['radio'] == -1 and default_radio != -1:
        d['radio'] = default_radio

    # Skip CDMA towers missing lac or cid (no psc on CDMA exists to
    # backfill using inference)
    if d['radio'] == RADIO_TYPE['cdma'] and (d['lac'] < 0 or d['cid'] < 0):
        return None

    # Treat cid=65535 without a valid lac as an unspecified value
    if d['lac'] == -1 and d['cid'] == 65535:
        d['cid'] = -1

    # Must have (lac and cid) or psc (psc-only to use in backfill)
    if (d['lac'] == -1 or d['cid'] == -1) and d['psc'] == -1:
        return None

    return d


def normalized_cell_measure_dict(d, measure_radio=-1):
    """
    Returns a normalized copy of the provided cell-measure dict d,
    or None if the dict was invalid.
    """
    d = normalized_cell_dict(d, default_radio=measure_radio)
    d = normalized_measure_dict(d)

    location_is_in_country = geocalc.location_is_in_country
    if d is not None:
        # Lat/lon must be inside one of the bounding boxes for the MCC.
        lat = float(d['lat'])
        lon = float(d['lon'])
        if not any([location_is_in_country(lat, lon, c.alpha2, 1)
                    for c in mobile_codes.mcc(str(d['mcc']))]):
            d = None

    if d is None:
        return None

    if 'asu' in d and 'signal' in d:
        # some clients send us a dBm value in the asu field, move it
        # over to the signal field before hitting validation
        if d['asu'] < -1 and d['signal'] == 0:
            d['signal'] = d['asu']
            d['asu'] = -1

    return normalized_dict(
        d, dict(asu=(0, 31, -1),
                signal=(-200, -1, 0),
                ta=(0, 63, 0)))
