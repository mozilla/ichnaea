from collections import defaultdict
import uuid

from sqlalchemy.sql import and_, or_

from ichnaea.async.task import DatabaseTask
from ichnaea.constants import (
    PERMANENT_BLACKLIST_THRESHOLD,
    TEMPORARY_BLACKLIST_DURATION,
)
from ichnaea.content.models import (
    MapStat,
    Score,
    SCORE_TYPE,
    User,
)
from ichnaea.customjson import (
    decode_datetime,
    loads,
)
from ichnaea.data.validation import (
    normalized_measure_dict,
    normalized_wifi_measure_dict,
    normalized_cell_measure_dict,
)
from ichnaea.geocalc import distance, centroid, range_to_points
from ichnaea.logging import get_stats_client
from ichnaea.models import (
    CELLID_LAC,
    Cell,
    CellBlacklist,
    CellKey,
    CellMeasure,
    RADIO_TYPE,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
    join_cellkey,
    join_wifikey,
    to_cellkey,
    to_cellkey_psc,
    to_wifikey,
)
from ichnaea import util
from ichnaea.worker import celery

WIFI_MAX_DIST_KM = 5
CELL_MAX_DIST_KM = 150


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


def blacklist_and_remove_moving_stations(session, blacklist_model,
                                         station_type, to_key, join_key,
                                         moving_stations, remove_station):
    moving_keys = []
    utcnow = util.utcnow()
    for station in moving_stations:
        key = to_key(station)
        query = session.query(blacklist_model).filter(
            *join_key(blacklist_model, key))
        b = query.first()
        d = key._asdict()
        moving_keys.append(d)
        if b:
            b.time = utcnow
            b.count += 1
        else:
            b = blacklist_model(**d)
            session.add(b)

    if moving_keys:
        get_stats_client().incr("items.blacklisted.%s_moving" % station_type,
                                len(moving_keys))
        remove_station.delay(moving_keys)


def blacklist_and_remove_moving_cells(session, moving_cells):
    blacklist_and_remove_moving_stations(session,
                                         blacklist_model=CellBlacklist,
                                         station_type="cell",
                                         to_key=to_cellkey,
                                         join_key=join_cellkey,
                                         moving_stations=moving_cells,
                                         remove_station=remove_cell)


def blacklist_and_remove_moving_wifis(session, moving_wifis):
    blacklist_and_remove_moving_stations(session,
                                         blacklist_model=WifiBlacklist,
                                         station_type="wifi",
                                         to_key=to_wifikey,
                                         join_key=join_wifikey,
                                         moving_stations=moving_wifis,
                                         remove_station=remove_wifi)


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


def calculate_new_position(station, measures, max_dist_km):
    # This function returns True if the station was found to be moving.
    length = len(measures)
    latitudes = [w[0] for w in measures]
    longitudes = [w[1] for w in measures]
    new_lat = sum(latitudes) / length
    new_lon = sum(longitudes) / length

    if station.lat and station.lon:
        latitudes.append(station.lat)
        longitudes.append(station.lon)
        existing_station = True
    else:
        station.lat = new_lat
        station.lon = new_lon
        existing_station = False

    # calculate extremes of measures, existing location estimate
    # and existing extreme values
    def extreme(vals, attr, function):
        new = function(vals)
        old = getattr(station, attr, None)
        if old is not None:
            return function(new, old)
        else:
            return new

    min_lat = extreme(latitudes, 'min_lat', min)
    min_lon = extreme(longitudes, 'min_lon', min)
    max_lat = extreme(latitudes, 'max_lat', max)
    max_lon = extreme(longitudes, 'max_lon', max)

    # calculate sphere-distance from opposite corners of
    # bounding box containing current location estimate
    # and new measurements; if too big, station is moving
    box_dist = distance(min_lat, min_lon, max_lat, max_lon)

    if existing_station:

        if box_dist > max_dist_km:
            # Signal a moving station and return early without updating
            # the station since it will be deleted by caller momentarily
            return True

        new_total = station.total_measures
        old_length = new_total - length

        station.lat = ((station.lat * old_length) +
                       (new_lat * length)) / new_total
        station.lon = ((station.lon * old_length) +
                       (new_lon * length)) / new_total

    # decrease new counter, total is already correct
    station.new_measures = station.new_measures - length

    # update max/min lat/lon columns
    station.min_lat = min_lat
    station.min_lon = min_lon
    station.max_lat = max_lat
    station.max_lon = max_lon

    # give radio-range estimate between extreme values and centroid
    ctr = (station.lat, station.lon)
    points = [(min_lat, min_lon),
              (min_lat, max_lon),
              (max_lat, min_lon),
              (max_lat, max_lon)]

    station.range = range_to_points(ctr, points) * 1000.0
    station.modified = util.utcnow()


def create_or_update_station(session, key, station_model,
                             join_key, utcnow, num):
    """
    Creates a station or updates its new/total_measures counts to reflect
    recently-received measures.
    """
    query = session.query(station_model).filter(
        *join_key(station_model, key))
    station = query.first()

    if station is not None:
        station.new_measures += num
        station.total_measures += num
    else:
        stmt = station_model.__table__.insert(
            on_duplicate='new_measures = new_measures + %s, '
                         'total_measures = total_measures + %s' % (num, num)
        ).values(
            created=utcnow,
            new_measures=num,
            total_measures=num,
            **key._asdict())
        session.execute(stmt)


def create_cell_measure(utcnow, entry):
    # creates a dict.copy() avoiding test leaks reusing the same
    # entries for multiple task calls
    entry = normalized_cell_measure_dict(entry)
    if entry is None:
        return None
    # add creation date
    entry['created'] = utcnow
    # decode from JSON compatible format
    entry['report_id'] = uuid.UUID(hex=entry['report_id']).bytes
    entry['time'] = decode_datetime(entry['time'])
    return CellMeasure(**entry)


def create_wifi_measure(utcnow, entry):
    # creates a dict.copy() avoiding test leaks reusing the same
    # entries for multiple task calls
    entry = normalized_wifi_measure_dict(entry)
    if entry is None:  # pragma: no cover
        return None
    # add creation date
    entry['created'] = utcnow
    # map internal date name to model name
    entry['snr'] = entry.pop('signalToNoiseRatio')
    # decode from JSON compatible format
    entry['report_id'] = uuid.UUID(hex=entry['report_id']).bytes
    entry['time'] = decode_datetime(entry['time'])
    return WifiMeasure(**entry)


def emit_new_measures_metric(stats_client, session, shortname,
                             model, min_new, max_new):
    q = session.query(model).filter(
        model.new_measures >= min_new,
        model.new_measures < max_new)
    n = q.count()
    stats_client.gauge('task.%s.new_measures_%d_%d' %
                       (shortname, min_new, max_new), n)


def incomplete_measure(key):
    """
    Certain incomplete measures we want to store in the database
    even though they should not lead to the creation of a station
    entry; these are cell measures with -1 for LAC and/or CID, and
    will be inferred from neighboring cells.
    """
    if hasattr(key, 'radio') and \
       (key.radio < 0 or key.lac < 0 or key.cid < 0):  # NOQA
        return True
    return False


def process_mapstat(session, positions):
    # Scale from floating point degrees to integer counts of thousandths of
    # a degree; 1/1000 degree is about 110m at the equator.
    factor = 1000
    today = util.utcnow().date()
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


def process_measure(data, session):
    def add_missing_dict_entries(dst, src):
        # x.update(y) overwrites entries in x with those in y;
        # We want to only add those not already present.
        # We also only want to copy the top-level base measure data
        # and not any nested values like cell or wifi.
        for (k, v) in src.items():
            if k != 'radio' and k not in dst \
               and not isinstance(v, (tuple, list, dict)):
                dst[k] = v

    measure_data = normalized_measure_dict(data)
    if measure_data is None:
        return ([], [])

    cell_measures = {}
    wifi_measures = {}
    measure_radio = RADIO_TYPE.get(data['radio'], -1)

    if data.get('cell'):
        # flatten measure / cell data into a single dict
        for c in data['cell']:
            add_missing_dict_entries(c, measure_data)
            c = normalized_cell_measure_dict(c, measure_radio)
            if c is None:  # pragma: no cover
                continue
            key = to_cellkey_psc(c)
            if key in cell_measures:  # pragma: no cover
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
            if key in wifi_measures:  # pragma: no cover
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
    positions = []
    cell_measures = []
    wifi_measures = []
    for i, item in enumerate(items):
        item['report_id'] = uuid.uuid1().hex
        cell, wifi = process_measure(item, session)
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

        # Create a task per group of 5 cell keys at a time.
        # Grouping them helps in avoiding per-task overhead.
        cells = list(cells.values())
        batch_size = 5
        countdown = 0
        for i in range(0, len(cells), batch_size):
            values = []
            for measures in cells[i:i + batch_size]:
                values.extend(measures)
            # insert measures, expire the task if it wasn't processed
            # after six hours to avoid queue overload, also delay
            # each task by one second more, to get a more even workload
            # and avoid parallel updates of the same underlying stations
            insert_measures_cell.apply_async(
                args=[values],
                kwargs={'userid': userid},
                expires=21600,
                countdown=countdown)
            countdown += 1

    if wifi_measures:
        # group by WiFi key
        stats_client.incr("items.uploaded.wifi_measures",
                          len(wifi_measures))
        wifis = defaultdict(list)
        for measure in wifi_measures:
            wifis[measure['key']].append(measure)

        # Create a task per group of 20 WiFi keys at a time.
        # We tend to get a huge number of unique WiFi networks per
        # batch upload, with one to very few measures per WiFi.
        # Grouping them helps in avoiding per-task overhead.
        wifis = list(wifis.values())
        batch_size = 20
        countdown = 0
        for i in range(0, len(wifis), batch_size):
            values = []
            for measures in wifis[i:i + batch_size]:
                values.extend(measures)
            # insert measures, expire the task if it wasn't processed
            # after six hours to avoid queue overload, also delay
            # each task by one second more, to get a more even workload
            # and avoid parallel updates of the same underlying stations
            insert_measures_wifi.apply_async(
                args=[values],
                kwargs={'userid': userid},
                expires=21600,
                countdown=countdown)
            countdown += 1

    if userid is not None:
        process_score(userid, len(positions), session)
    if positions:
        process_mapstat(session, positions)


def process_score(userid, points, session, key='location'):
    utcday = util.utcnow().date()
    query = session.query(Score).filter(
        Score.userid == userid).filter(
        Score.key == SCORE_TYPE[key]).filter(
        Score.time == utcday)
    score = query.first()
    if score is not None:
        score.value += int(points)
    else:
        stmt = Score.__table__.insert(
            on_duplicate='value = value + %s' % int(points)).values(
            userid=userid, key=SCORE_TYPE[key], time=utcday, value=points)
        session.execute(stmt)
    return points


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
        utcnow = util.utcnow()
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
            create_or_update_station(session, key, station_model,
                                     join_key, utcnow, num)

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


def update_enclosing_lacs(session, lacs, moving_cells, utcnow):
    moving_cell_ids = set([c.id for c in moving_cells])
    for lac_key, cells in lacs.items():
        if len(set([c.id for c in cells]) - moving_cell_ids) == 0:
            # All new cells are about to be removed, so don't bother
            # updating the lac
            continue
        q = session.query(Cell).filter(*join_cellkey(Cell, lac_key))
        lac = q.first()
        if lac is not None:  # pragma: no cover
            lac.new_measures += 1
        else:
            lac = Cell(
                radio=lac_key.radio,
                mcc=lac_key.mcc,
                mnc=lac_key.mnc,
                lac=lac_key.lac,
                cid=lac_key.cid,
                new_measures=1,
                total_measures=0,
                created=utcnow,
            )
            session.add(lac)

# End helper functions, start tasks


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
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True, queue='insert')
def insert_measures_cell(self, entries, userid=None,
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
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True, queue='insert')
def insert_measures_wifi(self, entries, userid=None,
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
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def location_update_cell(self, min_new=10, max_new=100, batch=10):
    try:
        utcnow = util.utcnow()
        cells = []
        with self.db_session() as session:
            emit_new_measures_metric(self.stats_client, session,
                                     self.shortname, Cell,
                                     min_new, max_new)
            query = session.query(Cell).filter(
                Cell.new_measures >= min_new).filter(
                Cell.new_measures < max_new).filter(
                Cell.cid != CELLID_LAC).limit(batch)
            cells = query.all()
            if not cells:
                return 0
            moving_cells = set()
            updated_lacs = defaultdict(list)
            for cell in cells:
                # skip cells with a missing lac/cid
                # or virtual LAC cells
                if cell.lac == -1 or cell.cid == -1 or \
                   cell.cid == CELLID_LAC:  # pragma: no cover
                    continue

                query = session.query(
                    CellMeasure.lat, CellMeasure.lon, CellMeasure.id).filter(
                    *join_cellkey(CellMeasure, cell))
                # only take the last X new_measures
                query = query.order_by(
                    CellMeasure.created.desc()).limit(
                    cell.new_measures)
                measures = query.all()

                if measures:
                    moving = calculate_new_position(
                        cell, measures, CELL_MAX_DIST_KM)
                    if moving:
                        moving_cells.add(cell)

                    updated_lacs[CellKey(cell.radio, cell.mcc,
                                         cell.mnc, cell.lac,
                                         CELLID_LAC)].append(cell)

            if updated_lacs:
                update_enclosing_lacs(session, updated_lacs,
                                      moving_cells, utcnow)

            if moving_cells:
                # some cells found to be moving too much
                blacklist_and_remove_moving_cells(session, moving_cells)

            session.commit()

        return (len(cells), len(moving_cells))
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def location_update_wifi(self, min_new=10, max_new=100, batch=10):
    try:
        wifis = {}
        with self.db_session() as session:
            emit_new_measures_metric(self.stats_client, session,
                                     self.shortname, Wifi,
                                     min_new, max_new)
            query = session.query(Wifi.key, Wifi).filter(
                Wifi.new_measures >= min_new).filter(
                Wifi.new_measures < max_new).limit(batch)
            wifis = dict(query.all())
            if not wifis:
                return 0
            moving_wifis = set()
            for wifi_key, wifi in wifis.items():
                # only take the last X new_measures
                measures = session.query(
                    WifiMeasure.lat, WifiMeasure.lon).filter(
                    WifiMeasure.key == wifi_key).order_by(
                    WifiMeasure.created.desc()).limit(
                    wifi.new_measures).all()
                if measures:
                    moving = calculate_new_position(
                        wifi, measures, WIFI_MAX_DIST_KM)
                    if moving:
                        moving_wifis.add(wifi)

            if moving_wifis:
                # some wifis found to be moving too much
                blacklist_and_remove_moving_wifis(session, moving_wifis)

            session.commit()
        return (len(wifis), len(moving_wifis))
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def remove_cell(self, cell_keys):
    cells_removed = 0
    try:
        with self.db_session() as session:
            changed_lacs = set()

            for k in cell_keys:
                key = to_cellkey(k)
                query = session.query(Cell).filter(*join_cellkey(Cell, key))
                cells_removed += query.delete()
                changed_lacs.add(key._replace(cid=CELLID_LAC))

            for key in changed_lacs:
                # Schedule an update to the enclosing LAC
                query = session.query(Cell).filter(*join_cellkey(Cell, key))
                lac = query.first()
                if lac is not None:
                    lac.new_measures += 1

            session.commit()
        return cells_removed
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def remove_wifi(self, wifi_keys):
    wifi_keys = set([w['key'] for w in wifi_keys])
    try:
        with self.db_session() as session:
            query = session.query(Wifi).filter(
                Wifi.key.in_(wifi_keys))
            wifis = query.delete(synchronize_session=False)
            session.commit()
        return wifis
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def scan_lacs(self, batch=100):
    """
    Find cell LACs that have changed and update the bounding box.

    """
    with self.db_session() as session:
        q = session.query(Cell).filter(
            Cell.cid == CELLID_LAC).filter(
            Cell.new_measures > 0).limit(batch)
        lacs = q.all()
        n = len(lacs)
        for lac in lacs:
            update_lac.delay(lac.radio, lac.mcc,
                             lac.mnc, lac.lac)
        session.commit()
        return n


@celery.task(base=DatabaseTask, bind=True)
def update_lac(self, radio, mcc, mnc, lac):
    try:
        with self.db_session() as session:
            # Select all the cells in this LAC that aren't the virtual
            # cell itself, and derive a bounding box for them.

            cell_query = session.query(Cell).filter(
                Cell.radio == radio).filter(
                Cell.mcc == mcc).filter(
                Cell.mnc == mnc).filter(
                Cell.lac == lac).filter(
                Cell.cid != CELLID_LAC).filter(
                Cell.new_measures == 0).filter(
                Cell.lat.isnot(None)).filter(
                Cell.lon.isnot(None))

            cells = cell_query.all()

            lac_query = session.query(Cell).filter(
                Cell.radio == radio).filter(
                Cell.mcc == mcc).filter(
                Cell.mnc == mnc).filter(
                Cell.lac == lac).filter(
                Cell.cid == CELLID_LAC)

            if len(cells) == 0:
                # If there are no more underlying cells, delete the lac entry
                lac_query.delete()
            else:
                # Otherwise update the lac entry based on all the cells
                lac = lac_query.first()

                points = [(c.lat, c.lon) for c in cells]
                min_lat = min([c.min_lat for c in cells])
                min_lon = min([c.min_lon for c in cells])
                max_lat = max([c.max_lat for c in cells])
                max_lon = max([c.max_lon for c in cells])

                bbox_points = [(min_lat, min_lon),
                               (min_lat, max_lon),
                               (max_lat, min_lon),
                               (max_lat, max_lon)]

                ctr = centroid(points)
                rng = range_to_points(ctr, bbox_points)

                # Switch units back to DB preferred centimicrodegres angle
                # and meters distance.
                ctr_lat = ctr[0]
                ctr_lon = ctr[1]
                rng = int(round(rng * 1000.0))

                # Now create or update the LAC virtual cell
                if lac is None:  # pragma: no cover
                    # This shouldn't happen, as this task is only called
                    # by scan_lacs, which only finds existing lac entries
                    lac = Cell(radio=radio,
                               mcc=mcc,
                               mnc=mnc,
                               lac=lac,
                               cid=CELLID_LAC,
                               lat=ctr_lat,
                               lon=ctr_lon,
                               range=rng)
                    session.add(lac)
                else:
                    lac.new_measures = 0
                    lac.lat = ctr_lat
                    lac.lon = ctr_lon
                    lac.range = rng

            session.commit()
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)
