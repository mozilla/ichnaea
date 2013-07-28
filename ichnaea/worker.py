from colander.iso8601 import parse_date

from ichnaea.db import Measure, RADIO_TYPE
from ichnaea.decimaljson import dumps, loads, to_precise_int


def _process_wifi(values):
    # convert frequency into channel numbers
    result = []
    for entry in values:
        # always remove frequency
        freq = entry.pop('frequency')
        # if no explicit channel was given, calculate
        if freq and not entry['channel']:
            if 2411 < freq < 2473:
                # 2.4 GHz band
                entry['channel'] = (freq - 2407) // 5
            elif 5169 < freq < 5826:
                # 5 GHz band
                entry['channel'] = (freq - 5000) // 5
        result.append(entry)
    return result


def insert_measures(measures, session):
    for data in measures:
        if isinstance(data, basestring):
            data = loads(data)
        measure = Measure()
        time = data['time']
        if isinstance(time, basestring):
            time = parse_date(time)
        measure.time = time
        measure.token = data['token']
        measure.lat = to_precise_int(data['lat'])
        measure.lon = to_precise_int(data['lon'])
        measure.accuracy = data['accuracy']
        measure.altitude = data['altitude']
        measure.altitude_accuracy = data['altitude_accuracy']
        if data.get('cell'):
            measure.radio = RADIO_TYPE.get(data['radio'], 0)
            measure.cell = dumps(data['cell'])
        if data.get('wifi'):
            measure.wifi = dumps(_process_wifi(data['wifi']))
        session.add(measure)
