from collections import (
    defaultdict,
    namedtuple,
)
import datetime

from celery.utils.log import get_task_logger
from colander import iso8601
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import and_, or_

from ichnaea.content.models import (
    MapStat,
    MAPSTAT_TYPE,
    User,
)
from ichnaea.models import (
    Cell,
    CellMeasure,
    Measure,
    normalize_wifi_key,
    RADIO_TYPE,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
)
from ichnaea.decimaljson import (
    dumps,
    loads,
    decode_datetime,
    encode_datetime,
    to_precise_int,
)
from ichnaea.service.submit.utils import process_score
from ichnaea.tasks import DatabaseTask
from ichnaea.worker import celery


logger = get_task_logger(__name__)
sql_null = None  # avoid pep8 warning

CellKey = namedtuple('CellKey', 'radio mcc mnc lac cid psc')


def process_mapstat_keyed(factor, stat_key, measures, session):
    tiles = defaultdict(int)
    # aggregate to tiles, according to factor
    for measure in measures:
        tiles[(measure.lat / factor, measure.lon / factor)] += 1
    query = session.query(MapStat.lat, MapStat.lon).filter(
        MapStat.key == stat_key)
    # dynamically construct a (lat, lon) in (list of tuples) filter
    # as MySQL isn't able to use indexes on such in queries
    lat_lon = []
    for (lat, lon) in tiles.keys():
        lat_lon.append(and_((MapStat.lat == lat), (MapStat.lon == lon)))
    query = query.filter(or_(*lat_lon))
    result = query.all()
    prior = {}
    for r in result:
        prior[(r[0], r[1])] = True
    tile_count = 0
    for (lat, lon), value in tiles.items():
        old = prior.get((lat, lon), False)
        if old:
            stmt = MapStat.__table__.update().where(
                MapStat.lat == lat).where(
                MapStat.lon == lon).where(
                MapStat.key == stat_key).values(
                value=MapStat.value + value)
        else:
            tile_count += 1
            stmt = MapStat.__table__.insert(
                on_duplicate='value = value + %s' % int(value)).values(
                lat=lat, lon=lon, key=stat_key, value=value)
        session.execute(stmt)
    return tile_count


def process_mapstat(measures, session, userid=None):
    # 10x10 meter tiles
    tile_count = process_mapstat_keyed(
        1000, MAPSTAT_TYPE['location'], measures, session)
    if userid is not None and tile_count > 0:
        process_score(userid, tile_count, session, key='new_location')
    # 100x100 m tiles
    process_mapstat_keyed(
        10000, MAPSTAT_TYPE['location_100m'], measures, session)


def process_user(nickname, session):
    userid = None
    if (2 <= len(nickname) <= 128):
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
    # cut down the time to a daily resolution
    measure['time'] = measure['time'].date()
    return measure


def process_measure(data, utcnow, session, userid=None):
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
    measure_data = dict(
        id=measure.id, created=encode_datetime(measure.created),
        lat=measure.lat, lon=measure.lon, time=encode_datetime(measure.time),
        accuracy=measure.accuracy, altitude=measure.altitude,
        altitude_accuracy=measure.altitude_accuracy,
        radio=measure.radio,
    )
    if data.get('cell'):
        insert_cell_measure.delay(measure_data, data['cell'], userid=userid)
        measure.cell = dumps(data['cell'])
    if data.get('wifi'):
        # filter out old-style sha1 hashes
        too_long_keys = False
        for w in data['wifi']:
            w['key'] = key = normalize_wifi_key(w['key'])
            if len(key) > 12:
                too_long_keys = True
                break
        if not too_long_keys:
            insert_wifi_measure.delay(
                measure_data, data['wifi'], userid=userid)
            measure.wifi = dumps(data['wifi'])
    return measure


@celery.task(base=DatabaseTask, bind=True)
def insert_measures(self, items=None, nickname=''):
    if not items:  # pragma: no cover
        return 0
    # TODO manually decode payload from our custom json
    items = loads(items)

    points = 0
    measures = []
    session_objects = []

    utcnow = datetime.datetime.utcnow().replace(tzinfo=iso8601.UTC)
    utcmin = utcnow - datetime.timedelta(60)

    try:
        with self.db_session() as session:
            userid, nickname = process_user(nickname, session)

            for item in items:
                item = process_time(item, utcnow, utcmin)
                measure = process_measure(item, utcnow, session, userid=userid)
                measures.append(measure)
                points += 1

            self.heka_client.incr("items.uploaded", count=len(measures))

            if userid is not None:
                process_score(userid, points, session)
            if measures:
                process_mapstat(measures, session, userid=userid)

            session.add_all(session_objects)
            session.commit()
        return len(measures)
    except IntegrityError as exc:  # pragma: no cover
        logger.exception('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


def create_cell_measure(measure_data, entry):
    # convert below-valid-range numbers to -1
    if 'mcc' not in entry or entry['mcc'] < 1:
        entry['mcc'] = -1
    if 'mnc' not in entry or entry['mnc'] < 0:
        entry['mnc'] = -1
    # some phones send maxint32 to signal "unknown"
    # convert to -1 as our canonical expression of "unknown"
    if 'lac' not in entry or entry['lac'] >= 2147483647:
        entry['lac'] = -1
    if 'cid' not in entry or entry['cid'] >= 2147483647:
        entry['cid'] = -1
    # make sure fields stay within reasonable bounds
    if 'asu' in entry and (entry['asu'] < 0 or entry['asu'] > 100):
        entry['asu'] = -1
    if 'signal' in entry and (entry['signal'] < -200 or entry['signal'] > -1):
        entry['signal'] = 0
    if 'ta' in entry and (entry['ta'] < 0 or entry['ta'] > 100):
        entry['ta'] = 0

    return CellMeasure(
        measure_id=measure_data['id'],
        created=decode_datetime(measure_data.get('created', '')),
        lat=measure_data['lat'],
        lon=measure_data['lon'],
        time=decode_datetime(measure_data.get('time', '')),
        accuracy=measure_data.get('accuracy', 0),
        altitude=measure_data.get('altitude', 0),
        altitude_accuracy=measure_data.get('altitude_accuracy', 0),
        mcc=entry.get('mcc', -1),
        mnc=entry.get('mnc', -1),
        lac=entry.get('lac', -1),
        cid=entry.get('cid', -1),
        psc=entry.get('psc', -1),
        asu=entry.get('asu', -1),
        signal=entry.get('signal', 0),
        ta=entry.get('ta', 0),
    )


def update_cell_measure_count(cell_key, count, created, session):
    # only update data for complete record
    if cell_key.radio < 0 or cell_key.mcc < 1 or cell_key.mnc < 0 or \
       cell_key.lac < 0 or cell_key.cid < 0:  # NOQA
        return 0

    # do we already know about this cell?
    query = session.query(Cell).filter(
        Cell.radio == cell_key.radio).filter(
        Cell.mcc == cell_key.mcc).filter(
        Cell.mnc == cell_key.mnc).filter(
        Cell.lac == cell_key.lac).filter(
        Cell.cid == cell_key.cid).filter(
        Cell.psc == cell_key.psc
    )

    cell = query.first()
    new_cell = 0
    if cell is None:
        new_cell = 1

    stmt = Cell.__table__.insert(
        on_duplicate='new_measures = new_measures + %s, '
                     'total_measures = total_measures + %s' % (count, count)
    ).values(
        created=created, radio=cell_key.radio,
        mcc=cell_key.mcc, mnc=cell_key.mnc, lac=cell_key.lac, cid=cell_key.cid,
        psc=cell_key.psc, new_measures=count, total_measures=count)
    session.execute(stmt)
    return new_cell


def process_cell_measure(session, measure_data, entries, userid=None):
    cell_count = defaultdict(int)
    cell_measures = []
    created = decode_datetime(measure_data.get('created', ''))

    # process entries
    for entry in entries:
        cell_measure = create_cell_measure(measure_data, entry)
        # use more specific cell type or
        # fall back to less precise measure
        if entry.get('radio'):
            cell_measure.radio = RADIO_TYPE.get(entry['radio'], -1)
        else:
            cell_measure.radio = measure_data['radio']
        cell_measures.append(cell_measure)
        # group per unique cell
        cell_count[CellKey(cell_measure.radio, cell_measure.mcc,
                           cell_measure.mnc, cell_measure.lac,
                           cell_measure.cid, cell_measure.psc)] += 1

    # update new/total measure counts
    new_cells = 0
    for cell_key, count in cell_count.items():
        new_cells += update_cell_measure_count(
            cell_key, count, created, session)

    # update user score
    if userid is not None and new_cells > 0:
        process_score(userid, new_cells, session, key='new_cell')

    session.add_all(cell_measures)
    return cell_measures


@celery.task(base=DatabaseTask, bind=True)
def insert_cell_measure(self, measure_data, entries, userid=None):
    try:
        cell_measures = []
        with self.db_session() as session:
            cell_measures = process_cell_measure(
                session, measure_data, entries, userid=userid)
            session.commit()
        return len(cell_measures)
    except IntegrityError as exc:  # pragma: no cover
        logger.exception('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


def convert_frequency(entry):
    freq = entry.pop('frequency', 0)
    # if no explicit channel was given, calculate
    if freq and not entry['channel']:
        if 2411 < freq < 2473:
            # 2.4 GHz band
            entry['channel'] = (freq - 2407) // 5
        elif 5169 < freq < 5826:
            # 5 GHz band
            entry['channel'] = (freq - 5000) // 5


def create_wifi_measure(measure_data, created, entry):
    return WifiMeasure(
        measure_id=measure_data['id'],
        created=created,
        lat=measure_data['lat'],
        lon=measure_data['lon'],
        time=decode_datetime(measure_data.get('time', '')),
        accuracy=measure_data.get('accuracy', 0),
        altitude=measure_data.get('altitude', 0),
        altitude_accuracy=measure_data.get('altitude_accuracy', 0),
        id=entry.get('id', None),
        key=entry['key'],
        channel=entry.get('channel', 0),
        signal=entry.get('signal', 0),
    )


def process_wifi_measure(session, measure_data, entries, userid=None):
    wifi_measures = []
    wifi_count = defaultdict(int)
    wifi_keys = set([e['key'] for e in entries])
    created = decode_datetime(measure_data.get('created', ''))

    # did we get measures for blacklisted wifis?
    blacked = session.query(WifiBlacklist.key).filter(
        WifiBlacklist.key.in_(wifi_keys)).all()
    blacked = set([b[0] for b in blacked])

    # process entries
    for entry in entries:
        wifi_key = entry['key']
        # convert frequency into channel numbers and remove frequency
        convert_frequency(entry)
        wifi_measures.append(create_wifi_measure(measure_data, created, entry))
        if wifi_key not in blacked:
            # skip blacklisted wifi AP's
            wifi_count[wifi_key] += 1

    # update user score
    if userid is not None:
        # do we already know about any wifis?
        white_keys = wifi_keys - blacked
        if white_keys:
            wifis = session.query(Wifi.key).filter(Wifi.key.in_(white_keys))
            wifis = dict([(w[0], True) for w in wifis.all()])
        else:
            wifis = {}
        # subtract known wifis from all unique wifis
        new_wifis = len(wifi_count) - len(wifis)
        if new_wifis > 0:
            process_score(userid, new_wifis, session, key='new_wifi')

    # update new/total measure counts
    for wifi_key, num in wifi_count.items():
        stmt = Wifi.__table__.insert(
            on_duplicate='new_measures = new_measures + %s, '
                         'total_measures = total_measures + %s' % (num, num)
        ).values(
            key=wifi_key, created=created,
            new_measures=num, total_measures=num)
        session.execute(stmt)

    session.add_all(wifi_measures)
    return wifi_measures


@celery.task(base=DatabaseTask, bind=True)
def insert_wifi_measure(self, measure_data, entries, userid=None):
    wifi_measures = []
    try:
        with self.db_session() as session:
            wifi_measures = process_wifi_measure(
                session, measure_data, entries, userid=userid)
            session.commit()
        return len(wifi_measures)
    except IntegrityError as exc:
        logger.exception('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)
