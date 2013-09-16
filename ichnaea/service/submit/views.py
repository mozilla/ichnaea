import datetime

from colander import iso8601
from cornice import Service
from pyramid.httpexceptions import HTTPNoContent

from ichnaea.db import (
    CellMeasure,
    Measure,
    normalize_wifi_key,
    RADIO_TYPE,
    Score,
    User,
)
from ichnaea.decimaljson import (
    dumps,
    encode_datetime,
    to_precise_int,
)
from ichnaea.service.error import (
    error_handler,
    MSG_ONE_OF,
)
from ichnaea.service.submit.schema import SubmitSchema
from ichnaea.tasks import insert_wifi_measure


def configure_submit(config):
    config.scan('ichnaea.service.submit.views')


def process_mapstat(measures, session):
    pass


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
            pass
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
            w['key'] = key = normalize_wifi_key(w['key'])
            if len(key) > 12:
                too_long_keys = True
                break
        if not too_long_keys:
            process_wifi(data['wifi'], measure)
            measure.wifi = dumps(data['wifi'])
    return (measure, session_objects)


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
    measures = []
    for item in request.validated['items']:
        item = process_time(item, utcnow, utcmin)
        measure, new_objects = process_measure(item, utcnow, session)
        measures.append(measure)
        session_objects.extend(new_objects)
        points += 1

    if userid is not None:
        process_score(userid, points, session)
    if measures:
        process_mapstat(measures, session)

    session.add_all(session_objects)
    session.commit()


def check_cell_or_wifi(data, request):
    cell = data.get('cell', ())
    wifi = data.get('wifi', ())
    if not any(wifi) and not any(cell):
        request.errors.add('body', 'body', MSG_ONE_OF)


def submit_validator(request):
    if len(request.errors):
        return
    for item in request.validated['items']:
        if not check_cell_or_wifi(item, request):
            # quit on first Error
            return


submit = Service(
    name='submit',
    path='/v1/submit',
    description="Submit a measurement result for a location.",
)


@submit.post(renderer='json', accept="application/json",
             schema=SubmitSchema, error_handler=error_handler,
             validators=submit_validator)
def submit_post(request):
    """
    Submit data about nearby cell towers and wifi base stations.

    An example request against URL::

        /v1/submit

    with a body of items:

    .. code-block:: javascript

        {'items': [
           {
            "lat": -22.7539192,
            "lon": -43.4371081,
            "time": "2012-03-15T11:12:13.456Z",
            "accuracy": 10,
            "altitude": 100,
            "altitude_accuracy": 1,
            "radio": "gsm",
            "cell": [
                {
                    "radio": "umts",
                    "mcc": 123,
                    "mnc": 123,
                    "lac": 12345,
                    "cid": 12345,
                    "signal": -60
                }
            ],
            "wifi": [
                {
                    "key": "3680873e9b83738eb72946d19e971e023e51fd01",
                    "channel": 11,
                    "frequency": 2412,
                    "signal": -50
                }
            ]
           }
           ]
        }

    The fields have the same meaning as explained in the search API.

    The only required fields are `lat` and `lon` and at least one cell or wifi
    entry.

    The altitude, accuracy and altitude_accuracy fields are all measured in
    meters. Altitude measures the height above or below the mean sea level,
    as defined by WGS 84.

    The timestamp has to be in UTC time, encoded in ISO 8601. If not
    provided, the server time will be used.

    On successful submission, you get a 204 status code back without any
    data in the body.

    If an error occurred, you get a 400 HTTP status code and a body of:

    .. code-block:: javascript

        {
            "errors": {}
        }

    The errors mapping contains detailed information about the errors.
    """
    submit_request(request)
    return HTTPNoContent()
