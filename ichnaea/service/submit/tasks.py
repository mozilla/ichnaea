from collections import (
    defaultdict,
    namedtuple,
)
import datetime

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
    valid_wifi_pattern,
    RADIO_TYPE,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
)
from ichnaea.decimaljson import (
    loads,
    decode_datetime,
    encode_datetime,
    to_precise_int,
)
from ichnaea.heka_logging import get_heka_client
from ichnaea.service.submit.utils import process_score
from ichnaea.tasks import DatabaseTask
from ichnaea.worker import celery


sql_null = None  # avoid pep8 warning

CellKey = namedtuple('CellKey', 'radio mcc mnc lac cid psc')


def process_mapstat_keyed(factor, stat_key, positions, session):
    tiles = defaultdict(int)
    # aggregate to tiles, according to factor
    for position in positions:
        tiles[(position['lat'] / factor, position['lon'] / factor)] += 1
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


def process_mapstat(positions, session, userid=None):
    # 10x10 meter tiles
    tile_count = process_mapstat_keyed(
        1000, MAPSTAT_TYPE['location'], positions, session)
    if userid is not None and tile_count > 0:
        process_score(userid, tile_count, session, key='new_location')
    # 100x100 m tiles
    process_mapstat_keyed(
        10000, MAPSTAT_TYPE['location_100m'], positions, session)


def process_user(nickname, session):
    userid = None
    if (2 <= len(nickname) <= 128):
        # automatically create user objects and update nickname
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
    # cut down the time to a monthly resolution
    measure['time'] = measure['time'].date().replace(day=1)
    return measure


def process_measure(measure_id, data):
    cell_measures = []
    wifi_measures = []
    measure_data = dict(
        measure_id=measure_id,
        lat=to_precise_int(data['lat']),
        lon=to_precise_int(data['lon']),
        time=encode_datetime(data['time']),
        accuracy=data['accuracy'],
        altitude=data['altitude'],
        altitude_accuracy=data['altitude_accuracy'],
    )
    measure_radio = RADIO_TYPE.get(data['radio'], -1)
    if data.get('cell'):
        # flatten measure / cell data into a single dict
        for c in data['cell']:
            c.update(measure_data)
            # use more specific cell type or
            # fall back to less precise measure
            if c['radio'] != '':
                c['radio'] = RADIO_TYPE.get(c['radio'], -1)
            else:
                c['radio'] = measure_radio
        cell_measures = data['cell']
    if data.get('wifi'):
        # filter out old-style sha1 hashes
        invalid_wifi_key = False
        for w in data['wifi']:
            w['key'] = key = normalize_wifi_key(w['key'])
            if not valid_wifi_pattern(key):
                invalid_wifi_key = True
                break

        if not invalid_wifi_key:
            # flatten measure / wifi data into a single dict
            for w in data['wifi']:
                w.update(measure_data)
            wifi_measures = data['wifi']
    return (cell_measures, wifi_measures)


def process_measures(items, archival_session, volatile_session, userid=None):
    utcnow = datetime.datetime.utcnow().replace(tzinfo=iso8601.UTC)
    utcmin = utcnow - datetime.timedelta(60)

    # get enough auto-increment ids assigned
    measures = []
    for i in range(len(items)):
        measure = Measure()
        measures.append(measure)
        archival_session.add(measure)
    # TODO switch unique measure id to a uuid, so we don't have to do
    # get these from a savepoint here
    archival_session.flush()

    positions = []
    cell_measures = []
    wifi_measures = []
    for i, item in enumerate(items):
        item = process_time(item, utcnow, utcmin)
        cell, wifi = process_measure(measures[i].id, item)
        cell_measures.extend(cell)
        wifi_measures.extend(wifi)
        positions.append({
            'lat': to_precise_int(item['lat']),
            'lon': to_precise_int(item['lon']),
        })

    heka_client = get_heka_client()

    if cell_measures:
        # group by and create task per cell key
        heka_client.incr("items.uploaded.cell_measures",
                         len(cell_measures))
        cells = defaultdict(list)
        for measure in cell_measures:
            cell_key = CellKey(measure['radio'], measure['mcc'],
                               measure['mnc'], measure['lac'],
                               measure['cid'], measure['psc'])
            cells[cell_key].append(measure)

        for values in cells.values():
            insert_cell_measures.delay(values, userid=userid)

    if wifi_measures:
        # group by and create task per wifi key
        heka_client.incr("items.uploaded.wifi_measures",
                         len(wifi_measures))
        wifis = defaultdict(list)
        for measure in wifi_measures:
            wifis[measure['key']].append(measure)

        for values in wifis.values():
            insert_wifi_measures.delay(values, userid=userid)

    if userid is not None:
        process_score(userid, len(items), volatile_session)
    if positions:
        process_mapstat(positions, volatile_session, userid=userid)


@celery.task(base=DatabaseTask, bind=True)
def insert_measures(self, items=None, nickname=''):
    if not items:  # pragma: no cover
        return 0
    items = loads(items)
    length = len(items)

    try:
        with self.archival_db_session() as a_session:
            with self.volatile_db_session() as v_session:
                userid, nickname = process_user(nickname, v_session)

                process_measures(items,
                                 archival_session=a_session,
                                 volatile_session=v_session,
                                 userid=userid)
                self.heka_client.incr("items.uploaded.batches", count=length)

                a_session.commit()
                v_session.commit()
        return length
    except IntegrityError as exc:  # pragma: no cover
        self.heka_client.raven('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


def create_cell_measure(utcnow, entry):
    # skip records with missing or invalid mcc or mnc
    if 'mcc' not in entry or entry['mcc'] < 1 or entry['mcc'] > 999:
        return
    if 'mnc' not in entry or entry['mnc'] < 0 or entry['mnc'] > 32767:
        return

    # Skip CDMA towers missing lac or cid (no psc on CDMA exists to
    # backfill using inference)
    if entry.get('radio', -1) == 1 and \
       (entry.get('lac', -1) < 0 or entry.get('cid', -1) < 0):
        return

    # some phones send maxint32 to signal "unknown"
    # ignore anything above the maximum valid values
    if 'lac' not in entry or entry['lac'] < 0 or entry['lac'] > 65535:
        entry['lac'] = -1
    if 'cid' not in entry or entry['cid'] < 0 or entry['cid'] > 268435455:
        entry['cid'] = -1
    if 'psc' not in entry or entry['psc'] < 0 or entry['psc'] > 512:
        entry['psc'] = -1

    # Must have LAC+CID or PSC
    if (entry['lac'] == -1 or entry['cid'] == -1) and entry['psc'] == -1:
        return

    # make sure fields stay within reasonable bounds
    if 'asu' not in entry or entry['asu'] < 0 or entry['asu'] > 100:
        entry['asu'] = -1
    if 'signal' not in entry or entry['signal'] < -200 or entry['signal'] > -1:
        entry['signal'] = 0
    if 'ta' not in entry or entry['ta'] < 0 or entry['ta'] > 100:
        entry['ta'] = 0

    return CellMeasure(
        measure_id=entry.get('measure_id'),
        created=utcnow,
        lat=entry['lat'],
        lon=entry['lon'],
        time=decode_datetime(entry.get('time', '')),
        accuracy=entry.get('accuracy', 0),
        altitude=entry.get('altitude', 0),
        altitude_accuracy=entry.get('altitude_accuracy', 0),
        radio=entry.get('radio', -1),
        mcc=entry.get('mcc', -1),
        mnc=entry.get('mnc', -1),
        lac=entry.get('lac', -1),
        cid=entry.get('cid', -1),
        psc=entry.get('psc', -1),
        asu=entry.get('asu', -1),
        signal=entry.get('signal', 0),
        ta=entry.get('ta', 0),
    )


def update_cell_measure_count(cell_key, count, utcnow, session):
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
        created=utcnow, radio=cell_key.radio,
        mcc=cell_key.mcc, mnc=cell_key.mnc, lac=cell_key.lac, cid=cell_key.cid,
        psc=cell_key.psc, new_measures=count, total_measures=count)
    session.execute(stmt)
    return new_cell


def process_cell_measures(entries, archival_session, volatile_session, userid=None,
                          max_measures_per_cell=11000):
    cell_count = defaultdict(int)
    cell_measures = []
    utcnow = datetime.datetime.utcnow().replace(tzinfo=iso8601.UTC)

    dropped_malformed = 0
    dropped_overflow = 0
    space_available = {}

    # process entries
    for entry in entries:

        cell_measure = create_cell_measure(utcnow, entry)
        if not cell_measure:
            dropped_malformed += 1
            continue

        cell_key = CellKey(cell_measure.radio, cell_measure.mcc,
                           cell_measure.mnc, cell_measure.lac,
                           cell_measure.cid, cell_measure.psc)

        # check if there's space for new measurement within per-cell maximum
        # note: old measures gradually expire, so this is an intake-rate limit
        if cell_key not in space_available:
            query = volatile_session.query(Cell.total_measures).filter(
                Cell.radio == cell_key.radio,
                Cell.mcc == cell_key.mcc,
                Cell.mnc == cell_key.mnc,
                Cell.lac == cell_key.lac,
                Cell.cid == cell_key.cid,
                Cell.psc == cell_key.psc)
            curr = query.first()
            if curr is not None:
                space_available[cell_key] = max_measures_per_cell - curr[0]
            else:
                space_available[cell_key] = max_measures_per_cell

        if space_available[cell_key] > 0:
            space_available[cell_key] -= 1
        else:
            dropped_overflow += 1
            continue

        # Possibly drop measure if we're receiving them too
        # quickly for this cell.
        query = volatile_session.query(Cell.total_measures).filter(
            Cell.radio == cell_measure.radio,
            Cell.mcc == cell_measure.mcc,
            Cell.mnc == cell_measure.mnc,
            Cell.lac == cell_measure.lac,
            Cell.cid == cell_measure.cid,
            Cell.psc == cell_measure.psc)
        total_measures = query.first()
        if total_measures is not None:
            if total_measures[0] > max_measures_per_cell:
                dropped_overflow += 1
                continue

        cell_measures.append(cell_measure)
        # group per unique cell
        cell_count[cell_key] += 1

    heka_client = get_heka_client()

    if dropped_malformed != 0:
        heka_client.incr("items.dropped.cell_ingress_malformed",
                         count=dropped_malformed)

    if dropped_overflow != 0:
        heka_client.incr("items.dropped.cell_ingress_overflow",
                         count=dropped_overflow)

    # update new/total measure counts
    new_cells = 0
    for cell_key, count in cell_count.items():
        new_cells += update_cell_measure_count(
            cell_key, count, utcnow, volatile_session)

    # update user score
    if userid is not None and new_cells > 0:
        process_score(userid, new_cells, volatile_session, key='new_cell')

    heka_client.incr("items.inserted.cell_measures",
                     count=len(cell_measures))
    archival_session.add_all(cell_measures)
    return cell_measures


@celery.task(base=DatabaseTask, bind=True)
def insert_cell_measures(self, entries, userid=None,
                         max_measures_per_cell=11000):
    try:
        cell_measures = []
        with self.archival_db_session() as a_session:
            with self.volatile_db_session() as v_session:
                cell_measures = process_cell_measures(
                    entries,
                    archival_session=a_session,
                    volatile_session=v_session,
                    userid=userid,
                    max_measures_per_cell=max_measures_per_cell)
                a_session.commit()
                v_session.commit()
                return len(cell_measures)
    except IntegrityError as exc:  # pragma: no cover
        self.heka_client.raven('error')
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


def create_wifi_measure(utcnow, entry):
    return WifiMeasure(
        measure_id=entry.get('measure_id'),
        created=utcnow,
        lat=entry['lat'],
        lon=entry['lon'],
        time=decode_datetime(entry.get('time', '')),
        accuracy=entry.get('accuracy', 0),
        altitude=entry.get('altitude', 0),
        altitude_accuracy=entry.get('altitude_accuracy', 0),
        key=entry['key'],
        channel=entry.get('channel', 0),
        signal=entry.get('signal', 0),
    )


def process_wifi_measures(entries,
                          archival_session,
                          volatile_session,
                          userid=None,
                          max_measures_per_wifi=11000):
    wifi_measures = []
    wifi_count = defaultdict(int)
    wifi_keys = set([e['key'] for e in entries])

    utcnow = datetime.datetime.utcnow().replace(tzinfo=iso8601.UTC)

    # did we get measures for blacklisted wifis?
    blacked = volatile_session.query(WifiBlacklist.key).filter(
        WifiBlacklist.key.in_(wifi_keys)).all()
    blacked = set([b[0] for b in blacked])

    space_available = {}
    dropped_overflow = 0

    # process entries
    for entry in entries:
        wifi_key = entry['key']

        # check if there's space for new measurement within per-AP maximum
        # note: old measures gradually expire, so this is an intake-rate limit
        if wifi_key not in space_available:
            query = volatile_session.query(Wifi.total_measures).filter(
                Wifi.key == wifi_key)
            curr = query.first()
            if curr is not None:
                space_available[wifi_key] = max_measures_per_wifi - curr[0]
            else:
                space_available[wifi_key] = max_measures_per_wifi

        if space_available[wifi_key] > 0:
            space_available[wifi_key] -= 1
        else:
            dropped_overflow += 1
            continue

        # convert frequency into channel numbers and remove frequency
        convert_frequency(entry)
        wifi_measures.append(create_wifi_measure(utcnow, entry))
        if wifi_key not in blacked:
            # skip blacklisted wifi AP's
            wifi_count[wifi_key] += 1

    heka_client = get_heka_client()

    if dropped_overflow != 0:
        heka_client.incr("items.dropped.wifi_ingress_overflow",
                         count=dropped_overflow)

    # update user score
    if userid is not None:
        # do we already know about any wifis?
        white_keys = wifi_keys - blacked
        if white_keys:
            wifis = volatile_session.query(Wifi.key).filter(
                Wifi.key.in_(white_keys))
            wifis = dict([(w[0], True) for w in wifis.all()])
        else:
            wifis = {}
        # subtract known wifis from all unique wifis
        new_wifis = len(wifi_count) - len(wifis)
        if new_wifis > 0:
            process_score(userid, new_wifis, volatile_session, key='new_wifi')

    # update new/total measure counts
    for wifi_key, num in wifi_count.items():
        stmt = Wifi.__table__.insert(
            on_duplicate='new_measures = new_measures + %s, '
                         'total_measures = total_measures + %s' % (num, num)
        ).values(
            key=wifi_key, created=utcnow,
            new_measures=num, total_measures=num)
        volatile_session.execute(stmt)

    heka_client.incr("items.inserted.wifi_measures",
                     count=len(wifi_measures))
    archival_session.add_all(wifi_measures)
    return wifi_measures


@celery.task(base=DatabaseTask, bind=True)
def insert_wifi_measures(self, entries, userid=None,
                         max_measures_per_wifi=11000):
    wifi_measures = []
    try:
        with self.archival_db_session() as a_session:
            with self.volatile_db_session() as v_session:
                wifi_measures = process_wifi_measures(
                    entries,
                    archival_session=a_session,
                    volatile_session=v_session,
                    userid=userid,
                    max_measures_per_wifi=max_measures_per_wifi)
                a_session.commit()
                v_session.commit()
                return len(wifi_measures)
    except IntegrityError as exc:  # pragma: no cover
        self.heka_client.raven('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)
