import datetime
import logging

from colander import iso8601
from colander.iso8601 import parse_date

from ichnaea.db import CellMeasure
from ichnaea.db import Measure
from ichnaea.db import RADIO_TYPE
from ichnaea.db import Score
from ichnaea.db import User
from ichnaea.db import WifiMeasure
from ichnaea.decimaljson import dumps
from ichnaea.decimaljson import to_precise_int

logger = logging.getLogger('ichnaea')


def process_user(token, nickname, session):
    userid = None
    if not (24 <= len(token) <= 36):
        # doesn't look like it's a uuid
        token = ""
        nickname = ""
    elif (3 <= len(nickname) <= 128):
        # automatically create user objects and update nickname
        if isinstance(nickname, str):
            nickname = nickname.decode('utf-8', 'ignore')
        rows = session.query(User).filter(User.token == token)
        old = rows.first()
        if old:
            # update nickname
            old.nickname = nickname
            userid = old.id
        else:
            user = User()
            user.token = token
            user.nickname = nickname
            session.add(user)
            session.flush()
            userid = user.id
    return (userid, token, nickname)


def process_score(userid, points, session):
    # TODO use select for update to lock the row
    rows = session.query(Score).filter(Score.userid == userid)
    old = rows.first()
    if old:
        # update score
        old.value = old.value + points
    else:
        score = Score()
        score.userid = userid
        score.value = points
        session.add(score)
    return points


def process_time(measure, utcnow, utcmin):
    try:
        measure['time'] = iso8601.parse_date(measure['time'])
    except (iso8601.ParseError, TypeError):
        if measure['time']:  # pragma: no cover
            # ignore debug log for empty values
            logger.debug('submit_time_error' + repr(measure['time']))
        measure['time'] = utcnow
    else:
        # don't accept future time values or
        # time values more than 60 days in the past
        if measure['time'] > utcnow or measure['time'] < utcmin:
            measure['time'] = utcnow
    return measure


def process_measure(data):
    session_objects = []
    measure = Measure()
    time = data['time']
    if isinstance(time, basestring):
        time = parse_date(time)
    measure.time = time
    measure.lat = to_precise_int(data['lat'])
    measure.lon = to_precise_int(data['lon'])
    measure.accuracy = data['accuracy']
    measure.altitude = data['altitude']
    measure.altitude_accuracy = data['altitude_accuracy']
    if data.get('cell'):
        measure.radio = RADIO_TYPE.get(data['radio'], 0)
        cells, cell_data = process_cell(data['cell'], measure)
        measure.cell = dumps(cell_data)
        session_objects.extend(cells)
    if data.get('wifi'):
        wifis, wifi_data = process_wifi(data['wifi'], measure)
        measure.wifi = dumps(wifi_data)
        session_objects.extend(wifis)

    session_objects.append(measure)
    return session_objects


def process_cell(entries, measure):
    result = []
    cells = []
    for entry in entries:
        cell = CellMeasure()
        cell.lat = measure.lat
        cell.lon = measure.lon
        cell.time = measure.time
        cell.accuracy = measure.accuracy
        cell.altitude = measure.altitude
        cell.altitude_accuracy = measure.altitude_accuracy
        cell.radio = measure.radio
        cell.mcc = entry['mcc']
        cell.mnc = entry['mnc']
        cell.lac = entry['lac']
        cell.cid = entry['cid']
        cell.psc = entry['psc']
        cell.asu = entry['asu']
        cell.signal = entry['signal']
        cell.ta = entry['ta']
        cells.append(cell)
        result.append(entry)
    return (cells, result)


def process_wifi(entries, measure):
    wifis = []
    result = []
    for entry in entries:
        # convert frequency into channel numbers and remove frequency
        freq = entry.pop('frequency', 0)
        # if no explicit channel was given, calculate
        if freq and not entry['channel']:
            if 2411 < freq < 2473:
                # 2.4 GHz band
                entry['channel'] = (freq - 2407) // 5
            elif 5169 < freq < 5826:
                # 5 GHz band
                entry['channel'] = (freq - 5000) // 5
        wifi = WifiMeasure()
        wifi.lat = measure.lat
        wifi.lon = measure.lon
        wifi.time = measure.time
        wifi.accuracy = measure.accuracy
        wifi.altitude = measure.altitude
        wifi.altitude_accuracy = measure.altitude_accuracy
        wifi.key = entry['key']
        wifi.channel = entry['channel']
        wifi.signal = entry['signal']
        wifis.append(wifi)
        result.append(entry)
    return (wifis, result)


def submit_request(request):
    session = request.database.session()
    session_objects = []

    token = request.headers.get('X-Token', '')
    nickname = request.headers.get('X-Nickname', '')
    userid, token, nickname = process_user(token, nickname, session)

    utcnow = datetime.datetime.utcnow().replace(tzinfo=iso8601.UTC)
    utcmin = utcnow - datetime.timedelta(60)

    points = 0
    for measure in request.validated['items']:
        measure = process_time(measure, utcnow, utcmin)
        session_objects.extend(process_measure(measure))
        points += 1

    if userid is not None:
        process_score(userid, points, session)

    session.add_all(session_objects)
    session.commit()
