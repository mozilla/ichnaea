from collections import defaultdict
import datetime
import uuid

from colander import iso8601
import pytz
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import and_, or_

from ichnaea.async.task import DatabaseTask
from ichnaea.content.models import (
    MapStat,
    User,
)
from ichnaea.models import (
    Cell,
    CellBlacklist,
    CellMeasure,
    normalized_wifi_measure_dict,
    normalized_cell_measure_dict,
    RADIO_TYPE,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
    join_cellkey,
    join_wifikey,
    to_cellkey_psc,
    to_wifikey,
    decode_datetime,
    encode_datetime,
    PERMANENT_BLACKLIST_THRESHOLD,
    TEMPORARY_BLACKLIST_DURATION,
)
from ichnaea.customjson import (
    loads,
)
from ichnaea.service.submit.utils import process_score
from ichnaea.stats import get_stats_client
from ichnaea.worker import celery


def process_mapstat(session, utcnow, positions):
    # Scale from floating point degrees to integer counts of thousandths of
    # a degree; 1/1000 degree is about 110m at the equator.
    factor = 1000
    today = utcnow.date()
    tiles = {}
    # aggregate to tiles, according to factor
    for position in positions:
        tiles[(int(position['lat'] * factor),
               int(position['lon'] * factor))] = True
    query = session.query(MapStat.lat, MapStat.lon)
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
    for (lat, lon) in tiles.keys():
        old = prior.get((lat, lon), False)
        if not old:
            stmt = MapStat.__table__.insert(
                on_duplicate='id = id').values(
                time=today, lat=lat, lon=lon)
            session.execute(stmt)


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


def process_measure(report_id, data, session):
    def add_missing_dict_entries(dst, src):
        # x.update(y) overwrites entries in x with those in y;
        # we want to only add those not already present
        for (k, v) in src.items():
            if k not in dst:
                dst[k] = v

    cell_measures = {}
    wifi_measures = {}
    measure_data = dict(
        report_id=report_id,
        lat=data['lat'],
        lon=data['lon'],
        heading=data.get('heading', -1.0),
        speed=data.get('speed', -1.0),
        time=encode_datetime(data['time']),
        accuracy=data.get('accuracy', 0),
        altitude=data.get('altitude', 0),
        altitude_accuracy=data.get('altitude_accuracy', 0),
    )
    measure_radio = RADIO_TYPE.get(data['radio'], -1)
    if data.get('cell'):
        # flatten measure / cell data into a single dict
        for c in data['cell']:
            add_missing_dict_entries(c, measure_data)
            c = normalized_cell_measure_dict(c, measure_radio)
            if c is None:
                continue
            key = to_cellkey_psc(c)
            if key in cell_measures:
                existing = cell_measures[key]
                if existing['ta'] > c['ta'] or \
                   (existing['signal'] != 0 and
                    existing['signal'] < c['signal']) or \
                   existing['asu'] < c['asu']:
                    cell_measures[key] = c
            else:
                cell_measures[key] = c
    cell_measures = cell_measures.values()

    # flatten measure / wifi data into a single dict
    if data.get('wifi'):
        for w in data['wifi']:
            add_missing_dict_entries(w, measure_data)
            w = normalized_wifi_measure_dict(w)
            if w is None:
                continue
            key = w['key']
            if key in wifi_measures:
                existing = wifi_measures[key]
                if existing['signal'] != 0 and \
                   existing['signal'] < w['signal']:
                    wifi_measures[key] = w
            else:
                wifi_measures[key] = w
        wifi_measures = wifi_measures.values()
    return (cell_measures, wifi_measures)


def process_measures(items, session, userid=None):
    stats_client = get_stats_client()
    utcnow = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
    utcmin = utcnow - datetime.timedelta(60)

    positions = []
    cell_measures = []
    wifi_measures = []
    for i, item in enumerate(items):
        item = process_time(item, utcnow, utcmin)
        report_id = uuid.uuid1().hex
        cell, wifi = process_measure(report_id, item, session)
        cell_measures.extend(cell)
        wifi_measures.extend(wifi)
        if cell or wifi:
            positions.append({
                'lat': item['lat'],
                'lon': item['lon'],
            })

    if cell_measures:
        # group by and create task per cell key
        stats_client.incr("items.uploaded.cell_measures",
                          len(cell_measures))
        cells = defaultdict(list)
        for measure in cell_measures:
            cells[to_cellkey_psc(measure)].append(measure)

        for values in cells.values():
            # insert measures, expire the task if it wasn't processed
            # after two hours to avoid queue overload
            insert_cell_measures.apply_async(
                args=[values],
                kwargs={'userid': userid},
                expires=7200)

    if wifi_measures:
        # group by WiFi key
        stats_client.incr("items.uploaded.wifi_measures",
                          len(wifi_measures))
        wifis = defaultdict(list)
        for measure in wifi_measures:
            wifis[measure['key']].append(measure)

        # Create a task per group of 5 WiFi keys at a time.
        # We tend to get a huge number of unique WiFi networks per
        # batch upload, with one to very few measures per WiFi.
        # Grouping them helps in avoiding per-task overhead.
        wifis = list(wifis.values())
        batch_size = 5
        for i in range(0, len(wifis), batch_size):
            values = []
            for measures in wifis[i:i + batch_size]:
                values.extend(measures)
            # insert measures, expire the task if it wasn't processed
            # after two hours to avoid queue overload
            insert_wifi_measures.apply_async(
                args=[values],
                kwargs={'userid': userid},
                expires=7200)

    if userid is not None:
        process_score(userid, len(positions), session)
    if positions:
        process_mapstat(session, utcnow, positions)


@celery.task(base=DatabaseTask, bind=True, queue='incoming')
def insert_measures(self, items=None, nickname=''):
    if not items:  # pragma: no cover
        return 0
    items = loads(items)
    length = len(items)

    try:
        with self.db_session() as session:
            userid, nickname = process_user(nickname, session)

            process_measures(items, session, userid=userid)
            self.stats_client.incr("items.uploaded.batches", count=length)

            session.commit()
        return length
    except IntegrityError as exc:  # pragma: no cover
        self.heka_client.raven('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


def available_station_space(session, key, station_model, join_key,
                            max_measures_per_station):
    # check if there's space for new measurements within per-station maximum
    # old measures are gradually backed up, so this is an intake-rate limit

    query = session.query(station_model.total_measures).filter(
        *join_key(station_model, key))
    curr = query.first()

    if curr is not None:
        return max_measures_per_station - curr[0]

    # Return None to signal no station record was found.
    return None


def incomplete_measure(key):
    """
    Certain incomplete measures we want to store in the database
    even though they should not lead to the creation of a station
    entry; these are cell measures with -1 for LAC and/or CID, and
    will be inferred from neighbouring cells.
    See ichnaea.backfill.tasks.
    """
    if hasattr(key, 'radio') and \
       (key.radio < 0 or key.lac < 0 or key.cid < 0):  # NOQA
        return True
    return False


def blacklisted_station(session, key, blacklist_model,
                        join_key, utcnow):

    query = session.query(blacklist_model).filter(
        *join_key(blacklist_model, key))
    b = query.first()
    if b is not None:
        age = utcnow - b.time
        temporarily_blacklisted = age < TEMPORARY_BLACKLIST_DURATION
        permanently_blacklisted = b.count >= PERMANENT_BLACKLIST_THRESHOLD
        if temporarily_blacklisted or permanently_blacklisted:
            return True
    return False


def create_or_update_station(session, key, station_model, utcnow, num):
    """
    Creates a station or updates its new/total_measures counts to reflect
    recently-received measures.
    """
    d = key._asdict()
    stmt = station_model.__table__.insert(
        on_duplicate='new_measures = new_measures + %s, '
                     'total_measures = total_measures + %s' % (num, num)
    ).values(
        created=utcnow,
        new_measures=num,
        total_measures=num,
        **d)
    session.execute(stmt)


def process_station_measures(session, entries, station_type,
                             station_model, measure_model, blacklist_model,
                             create_measure, create_key, join_key,
                             userid=None, max_measures_per_station=11000,
                             utcnow=None):

    all_measures = []
    dropped_blacklisted = 0
    dropped_malformed = 0
    dropped_overflow = 0
    stats_client = get_stats_client()
    new_stations = 0
    if utcnow is None:
        utcnow = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
    elif isinstance(utcnow, basestring):
        utcnow = decode_datetime(utcnow)

    # Process entries and group by validated station key
    station_measures = defaultdict(list)
    for entry in entries:
        measure = create_measure(utcnow, entry)

        if not measure:
            dropped_malformed += 1
            continue

        station_measures[create_key(measure)].append(measure)

    # Process measures one station at a time
    for key, measures in station_measures.items():

        incomplete = False
        is_new_station = False

        # Figure out how much space is left for this station.
        free = available_station_space(session, key, station_model,
                                       join_key, max_measures_per_station)
        if free is None:
            is_new_station = True
            free = max_measures_per_station

        if is_new_station:
            # Drop measures for blacklisted stations.
            if blacklisted_station(session, key, blacklist_model,
                                   join_key, utcnow):
                dropped_blacklisted += len(measures)
                continue

            incomplete = incomplete_measure(key)
            if not incomplete:
                # We discovered an actual new complete station.
                new_stations += 1

        # Accept measures up to input-throttling limit, then drop.
        num = 0
        for measure in measures:
            if free <= 0:
                dropped_overflow += 1
                continue
            all_measures.append(measure)
            free -= 1
            num += 1

        # Accept incomplete measures, just don't make stations for them.
        # (station creation is a side effect of count-updating)
        if not incomplete and num > 0:
            create_or_update_station(session, key, station_model, utcnow, num)

    # Credit the user with discovering any new stations.
    if userid is not None and new_stations > 0:
        process_score(userid, new_stations, session,
                      key='new_' + station_type)

    if dropped_blacklisted != 0:
        stats_client.incr(
            "items.dropped.%s_ingress_blacklisted" % station_type,
            count=dropped_blacklisted)

    if dropped_malformed != 0:
        stats_client.incr(
            "items.dropped.%s_ingress_malformed" % station_type,
            count=dropped_malformed)

    if dropped_overflow != 0:
        stats_client.incr(
            "items.dropped.%s_ingress_overflow" % station_type,
            count=dropped_overflow)

    stats_client.incr(
        "items.inserted.%s_measures" % station_type,
        count=len(all_measures))

    session.add_all(all_measures)
    return all_measures


def create_cell_measure(utcnow, entry):
    entry = normalized_cell_measure_dict(entry)
    if entry is None:
        return None
    report_id = entry.get('report_id')
    if report_id:
        report_id = uuid.UUID(hex=report_id).bytes
    return CellMeasure(
        report_id=report_id,
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
        heading=entry.get('heading', -1.0),
        speed=entry.get('speed', -1.0),
    )


def create_wifi_measure(utcnow, entry):
    entry = normalized_wifi_measure_dict(entry)
    if entry is None:
        return None
    report_id = entry.get('report_id')
    if report_id:
        report_id = uuid.UUID(hex=report_id).bytes
    return WifiMeasure(
        report_id=report_id,
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
        snr=entry.get('signalToNoiseRatio', 0),
        heading=entry.get('heading', -1.0),
        speed=entry.get('speed', -1.0),
    )


@celery.task(base=DatabaseTask, bind=True, queue='insert')
def insert_cell_measures(self, entries, userid=None,
                         max_measures_per_cell=11000,
                         utcnow=None):
    try:
        cell_measures = []
        with self.db_session() as session:
            cell_measures = process_station_measures(
                session, entries,
                station_type="cell",
                station_model=Cell,
                measure_model=CellMeasure,
                blacklist_model=CellBlacklist,
                create_measure=create_cell_measure,
                create_key=to_cellkey_psc,
                join_key=join_cellkey,
                userid=userid,
                max_measures_per_station=max_measures_per_cell,
                utcnow=utcnow)
            session.commit()
        return len(cell_measures)
    except IntegrityError as exc:  # pragma: no cover
        self.heka_client.raven('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True, queue='insert')
def insert_wifi_measures(self, entries, userid=None,
                         max_measures_per_wifi=11000,
                         utcnow=None):
    wifi_measures = []
    try:
        with self.db_session() as session:
            wifi_measures = process_station_measures(
                session, entries,
                station_type="wifi",
                station_model=Wifi,
                measure_model=WifiMeasure,
                blacklist_model=WifiBlacklist,
                create_measure=create_wifi_measure,
                create_key=to_wifikey,
                join_key=join_wifikey,
                userid=userid,
                max_measures_per_station=max_measures_per_wifi,
                utcnow=utcnow)
            session.commit()
        return len(wifi_measures)
    except IntegrityError as exc:  # pragma: no cover
        self.heka_client.raven('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)
