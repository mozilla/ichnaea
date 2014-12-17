from datetime import timedelta
import uuid

from colander import iso8601
import mobile_codes

from ichnaea.customjson import (
    encode_datetime,
)
from ichnaea import geocalc
from ichnaea.models import (
    MAX_RADIO_TYPE,
    MIN_RADIO_TYPE,
    RADIO_TYPE,
)
from ichnaea import util
from ichnaea.data.constants import (
    REQUIRED,
    MAX_LAT,
    MIN_LAT,
    MAX_ACCURACY,
    MIN_ALTITUDE,
    MAX_ALTITUDE,
    MAX_ALTITUDE_ACCURACY,
    MAX_HEADING,
    MAX_SPEED,
    ALL_VALID_MCCS,
    INVALID_WIFI_REGEX,
    VALID_WIFI_REGEX,
)


def valid_wifi_pattern(key):
    return INVALID_WIFI_REGEX.match(key) and \
        VALID_WIFI_REGEX.match(key) and len(key) == 12


def normalized_time(time):
    """
    Takes a string representation of a time value, validates and parses
    it and returns a JSON-friendly string representation of the normalized
    time.
    """
    now = util.utcnow()
    if not time:
        time = None

    try:
        time = iso8601.parse_date(time)
    except (iso8601.ParseError, TypeError):
        time = now
    else:
        # don't accept future time values or
        # time values more than 60 days in the past
        min_time = now - timedelta(days=60)
        if time > now or time < min_time:
            time = now
    # cut down the time to a monthly resolution
    time = time.date().replace(day=1)
    return encode_datetime(time)


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

    d['time'] = normalized_time(d.get('time', None))

    if 'report_id' not in d:
        d['report_id'] = uuid.uuid1().hex
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

    if d is None:  # pragma: no cover
        return None

    if 'key' not in d:  # pragma: no cover
        return None

    d['key'] = normalized_wifi_key(d['key'])

    if not valid_wifi_pattern(d['key']):
        return None

    d['channel'] = normalized_wifi_channel(d)
    d.pop('frequency', 0)

    if 'radio' in d:
        del d['radio']

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
    if not isinstance(d, dict):  # pragma: no cover
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

    # Skip GSM/LTE/UMTS towers with an invalid MNC
    if (d['radio'] in (
            RADIO_TYPE['gsm'], RADIO_TYPE['umts'], RADIO_TYPE['lte'])
            and d['mnc'] > 999):
        return None

    # Treat cid=65535 without a valid lac as an unspecified value
    if d['lac'] == -1 and d['cid'] == 65535:
        d['cid'] = -1

    # Must have (lac and cid) or psc (psc-only to use in backfill)
    if (d['lac'] == -1 or d['cid'] == -1) and d['psc'] == -1:
        return None

    # If the cell id >= 65536 then it must be a umts tower
    if d['cid'] >= 65536 and d['radio'] == RADIO_TYPE['gsm']:
        d['radio'] = RADIO_TYPE['umts']

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
        d, dict(asu=(0, 97, -1),
                signal=(-150, -1, 0),
                ta=(0, 63, 0)))
