import datetime
import logging

from colander import iso8601
from colander.iso8601 import parse_date

from ichnaea.db import User
from ichnaea.db import Measure
from ichnaea.db import RADIO_TYPE
from ichnaea.decimaljson import dumps
from ichnaea.decimaljson import loads
from ichnaea.decimaljson import to_precise_int

logger = logging.getLogger('ichnaea')


def handle_nickname(nickname, token, session):
    if (3 <= len(nickname) <= 128):
        # automatically create user objects and update nickname
        if isinstance(nickname, str):
            nickname = nickname.decode('utf-8', 'ignore')
        rows = session.query(User).filter(User.token == token)
        old = rows.first()
        if old:
            # update nickname
            old.nickname = nickname
        else:
            user = User()
            user.token = token
            user.nickname = nickname
            session.add(user)


def handle_time(measure, utcnow, token):
    try:
        measure['time'] = iso8601.parse_date(measure['time'])
    except (iso8601.ParseError, TypeError):
        if measure['time']:  # pragma: no cover
            # ignore debug log for empty values
            logger.debug('submit_time_error' + repr(measure['time']))
        measure['time'] = utcnow
    else:
        # don't accept future time values
        if measure['time'] > utcnow:
            measure['time'] = utcnow
    if token:
        measure['token'] = token


def submit_request(request):
    session = request.database.session()
    measures = []
    utcnow = datetime.datetime.utcnow().replace(tzinfo=iso8601.UTC)
    header_token = request.headers.get('X-Token', '')
    header_nickname = ''
    if not (24 <= len(header_token) <= 36):
        # doesn't look like it's a uuid
        header_token = ""
    else:
        header_nickname = request.headers.get('X-Nickname', '')
        handle_nickname(header_nickname, header_token, session)

    for measure in request.validated['items']:
        handle_time(measure, utcnow, header_token)
        measures.append(dumps(measure))

    insert_measures(measures, session)
    session.commit()


def process_wifi(values):
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
            measure.wifi = dumps(process_wifi(data['wifi']))
        session.add(measure)
