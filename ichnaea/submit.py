import datetime
import logging

from colander import iso8601

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
            user = User(token=token, nickname=nickname)
            session.add(user)
            session.flush()
            userid = user.id
    return (userid, token, nickname)


def process_score(userid, points, session):
    rows = session.query(Score).filter(Score.userid == userid).\
        limit(1).with_lockmode('update')
    old = rows.first()
    if old:
        # update score
        old.value = old.value + points
    else:
        score = Score(userid=userid, value=points)
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
    measure.time = data['time']
    measure.lat = to_precise_int(data['lat'])
    measure.lon = to_precise_int(data['lon'])
    measure.accuracy = data['accuracy']
    measure.altitude = data['altitude']
    measure.altitude_accuracy = data['altitude_accuracy']
    measure.radio = RADIO_TYPE.get(data['radio'], -1)
    if data.get('cell'):
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
        cell = CellMeasure(
            lat=measure.lat, lon=measure.lon, time=measure.time,
            accuracy=measure.accuracy, altitude=measure.altitude,
            altitude_accuracy=measure.altitude_accuracy,
            mcc=entry['mcc'], mnc=entry['mnc'], lac=entry['lac'],
            cid=entry['cid'], psc=entry['psc'], asu=entry['asu'],
            signal=entry['signal'], ta=entry['ta'],
        )
        # use more specific cell type or fall back to less precise measure
        if entry['radio']:
            cell.radio = RADIO_TYPE.get(entry['radio'], -1)
        else:
            cell.radio = measure.radio
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
        wifi = WifiMeasure(
            lat=measure.lat, lon=measure.lon, time=measure.time,
            accuracy=measure.accuracy, altitude=measure.altitude,
            altitude_accuracy=measure.altitude_accuracy,
            key=entry['key'], channel=entry['channel'], signal=entry['signal'],
        )
        wifis.append(wifi)
        result.append(entry)
    return (wifis, result)


def submit_request(request):
    session = request.db_master_session
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
