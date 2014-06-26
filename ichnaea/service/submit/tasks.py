from collections import defaultdict
import datetime
import uuid

from colander import iso8601
import pytz
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import and_, or_

from ichnaea.content.models import (
    MapStat,
    MAPSTAT_TYPE,
    User,
)
from ichnaea.models import (
    Cell,
    CellBlacklist,
    CellMeasure,
    Measure,
    normalized_wifi_measure_dict,
    normalized_cell_measure_dict,
    RADIO_TYPE,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
    join_cellkey,
    to_cellkey_psc,
    decode_datetime,
    encode_datetime,
    from_degrees,
)
from ichnaea.customjson import (
    loads,
)
from ichnaea.heka_logging import get_heka_client
from ichnaea.service.submit.utils import process_score
from ichnaea.tasks import DatabaseTask
from ichnaea.worker import celery


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


def process_measure(report_id, measure_id, data, session):
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
        measure_id=measure_id,
        lat=from_degrees(data['lat']),
        lon=from_degrees(data['lon']),
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
    utcnow = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
    utcmin = utcnow - datetime.timedelta(60)

    # get enough auto-increment ids assigned
    measures = []
    for i in range(len(items)):
        measure = Measure()
        measures.append(measure)
        session.add(measure)
    # TODO switch unique measure id to a uuid, so we don't have to do
    # get these from a savepoint here
    session.flush()

    positions = []
    cell_measures = []
    wifi_measures = []
    for i, item in enumerate(items):
        item = process_time(item, utcnow, utcmin)
        report_id = uuid.uuid1().hex
        cell, wifi = process_measure(report_id, measures[i].id, item, session)
        cell_measures.extend(cell)
        wifi_measures.extend(wifi)
        positions.append({
            'lat': from_degrees(item['lat']),
            'lon': from_degrees(item['lon']),
        })

    heka_client = get_heka_client()

    if cell_measures:
        # group by and create task per cell key
        heka_client.incr("items.uploaded.cell_measures",
                         len(cell_measures))
        cells = defaultdict(list)
        for measure in cell_measures:
            cells[to_cellkey_psc(measure)].append(measure)

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
        process_score(userid, len(items), session)
    if positions and (cell_measures or wifi_measures):
        process_mapstat(positions, session, userid=userid)


@celery.task(base=DatabaseTask, bind=True)
def insert_measures(self, items=None, nickname=''):
    if not items:  # pragma: no cover
        return 0
    items = loads(items)
    length = len(items)

    try:
        with self.db_session() as session:
            userid, nickname = process_user(nickname, session)

            process_measures(items, session, userid=userid)
            self.heka_client.incr("items.uploaded.batches", count=length)

            session.commit()
        return length
    except IntegrityError as exc:  # pragma: no cover
        self.heka_client.raven('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


def throttled_station(session, key, space_available, station_model,
                      join_key, max_measures_per_station):
    # check if there's space for new measurement within per-station maximum
    # note: old measures gradually expire, so this is an intake-rate limit
    if key not in space_available:
        query = session.query(station_model.total_measures).filter(
            *join_key(station_model, key))
        curr = query.first()
        if curr is not None:
            space_available[key] = max_measures_per_station - curr[0]
        else:
            space_available[key] = max_measures_per_station

    if space_available[key] > 0:
        space_available[key] -= 1
        return False
    else:
        return True


def blacklisted_or_incomplete_station(session, key, blacked, blacklist_model,
                                      join_key):

    if isinstance(key, tuple) and \
       (key.radio < 0 or key.lac < 0 or key.cid < 0):  # NOQA
        return True

    if key not in blacked:
        query = session.query(blacklist_model).filter(
            *join_key(blacklist_model, key))
        b = query.first()
        blacked[key] = (b is not None)
    return blacked[key]


def update_station_measure_counts(session, userid, station_type,
                                  station_model, utcnow,
                                  station_count, is_new_station):

    # Credit the user with discovering any new stations.
    if userid is not None:
        new_station_count = len(filter(lambda x: x, is_new_station.values()))
        if new_station_count > 0:
            process_score(userid, new_station_count, session,
                          key='new_' + station_type)

    # Update new/total measure counts
    for key, num in station_count.items():
        if isinstance(key, tuple):
            d = key._asdict()
        else:
            d = {'key': key}
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
                             userid=None, max_measures_per_station=11000,):

    station_count = defaultdict(int)
    station_measures = []
    utcnow = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
    blacked = {}
    dropped_malformed = 0
    dropped_overflow = 0
    space_available = {}
    is_new_station = {}

    # Process entries
    for entry in entries:

        measure = create_measure(utcnow, entry)

        if not measure:
            dropped_malformed += 1
            continue

        key = create_key(measure)

        # We _drop_ throttled measures before they hit the database.
        if throttled_station(session, key, space_available, station_model,
                             join_key, max_measures_per_station):
            dropped_overflow += 1
            continue

        station_measures.append(measure)

        # We _accept_ blacklisted and incomplete measures into the
        # database, we just overlook them during position estimation (much
        # later: see ichnaea.tasks.*_location_update).
        if blacklisted_or_incomplete_station(session, key, blacked,
                                             blacklist_model, join_key):
            is_new_station[key] = False
        else:
            station_count[key] += 1
            if key not in is_new_station:
                q = session.query(station_model.id).filter(
                    *join_key(station_model, key))
                is_new_station[key] = (q.first() is None)

    heka_client = get_heka_client()

    if dropped_malformed != 0:
        heka_client.incr("items.dropped.%s_ingress_malformed" % station_type,
                         count=dropped_malformed)

    if dropped_overflow != 0:
        heka_client.incr("items.dropped.%s_ingress_overflow" % station_type,
                         count=dropped_overflow)

    update_station_measure_counts(session, userid, station_type,
                                  station_model, utcnow,
                                  station_count, is_new_station)

    heka_client.incr("items.inserted.%s_measures" % station_type,
                     count=len(station_measures))
    session.add_all(station_measures)
    return station_measures


def create_cell_measure(utcnow, entry):
    entry = normalized_cell_measure_dict(entry)
    if entry is None:
        return None
    report_id = entry.get('report_id')
    if report_id:
        report_id = uuid.UUID(hex=report_id).bytes
    return CellMeasure(
        report_id=report_id,
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
        snr=entry.get('signalToNoiseRatio', 0),
        heading=entry.get('heading', -1.0),
        speed=entry.get('speed', -1.0),
    )


@celery.task(base=DatabaseTask, bind=True)
def insert_cell_measures(self, entries, userid=None,
                         max_measures_per_cell=11000):
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
                max_measures_per_station=max_measures_per_cell)
            session.commit()
        return len(cell_measures)
    except IntegrityError as exc:  # pragma: no cover
        self.heka_client.raven('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def insert_wifi_measures(self, entries, userid=None,
                         max_measures_per_wifi=11000):
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
                create_key=lambda m: m.key,
                join_key=lambda m, k: (m.key == k,),
                userid=userid,
                max_measures_per_station=max_measures_per_wifi)
            session.commit()
        return len(wifi_measures)
    except IntegrityError as exc:  # pragma: no cover
        self.heka_client.raven('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)
