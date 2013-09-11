import datetime
import logging

from colander import iso8601

from ichnaea.db import (
    CellMeasure,
    Measure,
    RADIO_TYPE,
    Score,
    User,
)
from ichnaea.decimaljson import (
    dumps,
    encode_datetime,
    to_precise_int,
)
from ichnaea.tasks import insert_wifi_measure


logger = logging.getLogger('ichnaea')


def process_user(nickname, session):
    userid = None
    if (3 <= len(nickname) <= 128):
        # automatically create user objects and update nickname
        if isinstance(nickname, str):
            nickname = nickname.decode('utf-8', 'ignore')
        rows = session.query(User).filter(User.nickname == nickname)
        old = rows.first()
        if not old:
            user = User(nickname=nickname)
            session.add(user)
            session.flush()
            userid = user.id
        else:
            userid = old.id
    return (userid, nickname)


def process_score(userid, points, session):
    rows = session.query(Score).filter(Score.userid == userid).\
        limit(1).with_lockmode('update')
    old = rows.first()
    if old:
        # update score
        old.value = Score.value + points
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


def process_measure(data, utcnow, session):
    session_objects = []
    measure = Measure()
    measure.created = utcnow
    measure.time = data['time']
    measure.lat = to_precise_int(data['lat'])
    measure.lon = to_precise_int(data['lon'])
    measure.accuracy = data['accuracy']
    measure.altitude = data['altitude']
    measure.altitude_accuracy = data['altitude_accuracy']
    measure.radio = RADIO_TYPE.get(data['radio'], -1)
    # get measure.id set
    session.add(measure)
    session.flush()
    if data.get('cell'):
        cells, cell_data = process_cell(data['cell'], measure)
        measure.cell = dumps(cell_data)
        session_objects.extend(cells)
    if data.get('wifi'):
        # filter out old-style sha1 hashes
        too_long_keys = False
        for w in data['wifi']:
            if len(w['key']) > 17:
                too_long_keys = True
                break
        if not too_long_keys:
            process_wifi(data['wifi'], measure)
            measure.wifi = dumps(data['wifi'])
    return session_objects


def process_cell(entries, measure):
    result = []
    cells = []
    for entry in entries:
        cell = CellMeasure(
            measure_id=measure.id, created=measure.created,
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
    measure_data = dict(
        id=measure.id, created=encode_datetime(measure.created),
        lat=measure.lat, lon=measure.lon, time=encode_datetime(measure.time),
        accuracy=measure.accuracy, altitude=measure.altitude,
        altitude_accuracy=measure.altitude_accuracy,
    )
    insert_wifi_measure.delay(measure_data, entries)


def submit_request(request):
    session = request.db_master_session
    session_objects = []

    nickname = request.headers.get('X-Nickname', '')
    userid, nickname = process_user(nickname, session)

    utcnow = datetime.datetime.utcnow().replace(tzinfo=iso8601.UTC)
    utcmin = utcnow - datetime.timedelta(60)

    points = 0
    for measure in request.validated['items']:
        measure = process_time(measure, utcnow, utcmin)
        session_objects.extend(process_measure(measure, utcnow, session))
        points += 1

    if userid is not None:
        process_score(userid, points, session)

    session.add_all(session_objects)
    session.commit()
