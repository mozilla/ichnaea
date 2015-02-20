from collections import defaultdict
import uuid

from sqlalchemy.orm import load_only
from sqlalchemy.sql import and_, or_

from ichnaea.async.task import DatabaseTask
from ichnaea.constants import (
    PERMANENT_BLACKLIST_THRESHOLD,
    TEMPORARY_BLACKLIST_DURATION,
)
from ichnaea.models.content import (
    MapStat,
    Score,
    ScoreKey,
    User,
)
from ichnaea.customjson import (
    kombu_dumps,
    kombu_loads,
)
from ichnaea.data.schema import ValidCellKeySchema
from ichnaea.geocalc import distance, centroid, range_to_points
from ichnaea.logging import get_stats_client
from ichnaea.models import (
    Cell,
    CELL_MODEL_KEYS,
    CellAreaKey,
    CellBlacklist,
    CellKeyPscMixin,
    CellObservation,
    ReportMixin,
    Wifi,
    WifiBlacklist,
    WifiKeyMixin,
    WifiObservation,
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

UPDATE_KEY = {
    'cell': 'update_cell',
    'cell_lac': 'update_cell_lac',
    'wifi': 'update_wifi',
}


def enqueue_lacs(session, redis_client, lac_keys,
                 pipeline_key, expire=86400, batch=100):
    pipe = redis_client.pipeline()
    lac_json = [str(kombu_dumps(lac)) for lac in lac_keys]

    while lac_json:
        pipe.lpush(pipeline_key, *lac_json[:batch])
        lac_json = lac_json[batch:]

    # Expire key after 24 hours
    pipe.expire(pipeline_key, expire)
    pipe.execute()


def dequeue_lacs(redis_client, pipeline_key, batch=100):
    pipe = redis_client.pipeline()
    pipe.multi()
    pipe.lrange(pipeline_key, 0, batch - 1)
    pipe.ltrim(pipeline_key, batch, -1)
    return [kombu_loads(item) for item in pipe.execute()[0]]


def available_station_space(session, key, station_model, join_key,
                            max_observations_per_station):
    # check if there's space for new observations within per-station maximum
    # old observations are gradually backed up, so this is an intake-rate limit

    query = session.query(station_model.total_measures).filter(
        *join_key(station_model, key))
    curr = query.first()

    if curr is not None:
        return max_observations_per_station - curr[0]

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
        blacklisted_station = query.first()
        station_key = key._asdict()
        moving_keys.append(station_key)
        if blacklisted_station:
            blacklisted_station.time = utcnow
            blacklisted_station.count += 1
        else:
            blacklisted_station = blacklist_model(
                time=utcnow,
                count=1,
                **station_key)
            session.add(blacklisted_station)

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

    query = (session.query(blacklist_model)
                    .options(load_only('count', 'time'))
                    .filter(*join_key(blacklist_model, key)))
    black = query.first()
    if black is not None:
        age = utcnow - black.time
        temporarily_blacklisted = age < TEMPORARY_BLACKLIST_DURATION
        permanently_blacklisted = black.count >= PERMANENT_BLACKLIST_THRESHOLD
        if temporarily_blacklisted or permanently_blacklisted:
            return (True, black.time)
        return (False, black.time)
    return (False, None)


def calculate_new_position(station, observations, max_dist_km):
    # This function returns True if the station was found to be moving.
    length = len(observations)
    latitudes = [obs[0] for obs in observations]
    longitudes = [obs[1] for obs in observations]
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

    # calculate extremes of observations, existing location estimate
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
    # and new observations; if too big, station is moving
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
                             join_key, utcnow, num, first_blacklisted):
    """
    Creates a station or updates its new/total_measures counts to reflect
    recently-received observations.
    """
    query = (session.query(station_model)
                    .filter(*join_key(station_model, key)))
    station = query.first()

    if station is not None:
        station.new_measures += num
        station.total_measures += num
    else:
        created = utcnow
        if first_blacklisted:
            # if the station did previously exist, retain at least the
            # time it was first put on a blacklist as the creation date
            created = first_blacklisted
        stmt = station_model.__table__.insert(
            on_duplicate='new_measures = new_measures + %s, '
                         'total_measures = total_measures + %s' % (num, num)
        ).values(
            created=created,
            modified=utcnow,
            range=0,
            new_measures=num,
            total_measures=num,
            **key._asdict())
        session.execute(stmt)


def emit_new_observation_metric(stats_client, session, shortname,
                                model, min_new, max_new):
    q = session.query(model).filter(
        model.new_measures >= min_new,
        model.new_measures < max_new)
    n = q.count()
    stats_client.gauge('task.%s.new_measures_%d_%d' %
                       (shortname, min_new, max_new), n)


def incomplete_observation(station_type, key):
    """
    Certain incomplete observations we want to store in the database
    even though they should not lead to the creation of a station
    entry; these are cell observations with a missing value for
    LAC and/or CID, and will be inferred from neighboring cells.
    """
    if station_type == 'cell':
        schema = ValidCellKeySchema()
        for field in ('radio', 'lac', 'cid'):
            if getattr(key, field, None) == schema.fields[field].missing:
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


def process_user(nickname, email, session):
    userid = None
    if len(email) > 255:
        email = ''
    if (2 <= len(nickname) <= 128):
        # automatically create user objects and update nickname
        rows = session.query(User).filter(User.nickname == nickname)
        old = rows.first()
        if not old:
            user = User(
                nickname=nickname,
                email=email
            )
            session.add(user)
            session.flush()
            userid = user.id
        else:
            userid = old.id
            # update email column on existing user
            if old.email != email:
                old.email = email

    return (userid, nickname, email)


def process_observation(data, session):
    def add_missing_dict_entries(dst, src):
        # x.update(y) overwrites entries in x with those in y;
        # We want to only add those not already present.
        # We also only want to copy the top-level base report data
        # and not any nested values like cell or wifi.
        for (key, value) in src.items():
            if key != 'radio' and key not in dst \
               and not isinstance(value, (tuple, list, dict)):
                dst[key] = value

    report_data = ReportMixin.validate(data)
    if report_data is None:
        return ([], [])

    cell_observations = {}
    wifi_observations = {}

    if data.get('cell'):
        # flatten report / cell data into a single dict
        for cell in data['cell']:
            # only validate the additional fields
            cell = CellKeyPscMixin.validate(cell)
            if cell is None:  # pragma: no cover
                continue
            add_missing_dict_entries(cell, report_data)
            cell_key = to_cellkey_psc(cell)
            if cell_key in cell_observations:  # pragma: no cover
                existing = cell_observations[cell_key]
                if existing['ta'] > cell['ta'] or \
                   (existing['signal'] != 0 and
                    existing['signal'] < cell['signal']) or \
                   existing['asu'] < cell['asu']:
                    cell_observations[cell_key] = cell
            else:
                cell_observations[cell_key] = cell
    cell_observations = cell_observations.values()

    # flatten report / wifi data into a single dict
    if data.get('wifi'):
        for wifi in data['wifi']:
            # only validate the additional fields
            wifi = WifiKeyMixin.validate(wifi)
            if wifi is None:
                continue
            add_missing_dict_entries(wifi, report_data)
            wifi_key = wifi['key']
            if wifi_key in wifi_observations:  # pragma: no cover
                existing = wifi_observations[wifi_key]
                if existing['signal'] != 0 and \
                   existing['signal'] < wifi['signal']:
                    wifi_observations[wifi_key] = wifi
            else:
                wifi_observations[wifi_key] = wifi
        wifi_observations = wifi_observations.values()
    return (cell_observations, wifi_observations)


def process_observations(observations, session, userid=None,
                         api_key_log=False, api_key_name=None):
    stats_client = get_stats_client()
    positions = []
    cell_observations = []
    wifi_observations = []
    for i, obs in enumerate(observations):
        obs['report_id'] = uuid.uuid1()
        cell, wifi = process_observation(obs, session)
        cell_observations.extend(cell)
        wifi_observations.extend(wifi)
        if cell or wifi:
            positions.append({
                'lat': obs['lat'],
                'lon': obs['lon'],
            })

    if cell_observations:
        # group by and create task per cell key
        stats_client.incr('items.uploaded.cell_observations',
                          len(cell_observations))
        if api_key_log:
            stats_client.incr(
                'items.api_log.%s.uploaded.cell_observations' % api_key_name,
                len(cell_observations))

        cells = defaultdict(list)
        for obs in cell_observations:
            cells[to_cellkey_psc(obs)].append(obs)

        # Create a task per group of 5 cell keys at a time.
        # Grouping them helps in avoiding per-task overhead.
        cells = list(cells.values())
        batch_size = 5
        countdown = 0
        for i in range(0, len(cells), batch_size):
            values = []
            for observations in cells[i:i + batch_size]:
                values.extend(observations)
            # insert observations, expire the task if it wasn't processed
            # after six hours to avoid queue overload, also delay
            # each task by one second more, to get a more even workload
            # and avoid parallel updates of the same underlying stations
            insert_measures_cell.apply_async(
                args=[values],
                kwargs={'userid': userid},
                expires=21600,
                countdown=countdown)
            countdown += 1

    if wifi_observations:
        # group by WiFi key
        stats_client.incr('items.uploaded.wifi_observations',
                          len(wifi_observations))
        if api_key_log:
            stats_client.incr(
                'items.api_log.%s.uploaded.wifi_observations' % api_key_name,
                len(wifi_observations))

        wifis = defaultdict(list)
        for obs in wifi_observations:
            wifis[obs['key']].append(obs)

        # Create a task per group of 20 WiFi keys at a time.
        # We tend to get a huge number of unique WiFi networks per
        # batch upload, with one to very few observations per WiFi.
        # Grouping them helps in avoiding per-task overhead.
        wifis = list(wifis.values())
        batch_size = 20
        countdown = 0
        for i in range(0, len(wifis), batch_size):
            values = []
            for observations in wifis[i:i + batch_size]:
                values.extend(observations)
            # insert observations, expire the task if it wasn't processed
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
        Score.key == ScoreKey[key]).filter(
        Score.time == utcday)
    score = query.first()
    if score is not None:
        score.value += int(points)
    else:
        stmt = Score.__table__.insert(
            on_duplicate='value = value + %s' % int(points)).values(
            userid=userid, key=ScoreKey[key], time=utcday, value=points)
        session.execute(stmt)
    return points


def process_station_observations(session, entries, station_type,
                                 station_model, observation_model,
                                 blacklist_model, create_key, join_key,
                                 userid=None,
                                 max_observations_per_station=11000,
                                 utcnow=None):

    all_observations = []
    dropped_blacklisted = 0
    dropped_malformed = 0
    dropped_overflow = 0
    stats_client = get_stats_client()
    new_stations = 0
    if utcnow is None:
        utcnow = util.utcnow()

    # Process entries and group by validated station key
    station_observations = defaultdict(list)
    for entry in entries:
        entry['created'] = utcnow
        obs = observation_model.create(entry)

        if not obs:
            dropped_malformed += 1
            continue

        station_observations[create_key(obs)].append(obs)

    # Process observations one station at a time
    for key, observations in station_observations.items():

        first_blacklisted = None
        incomplete = False
        is_new_station = False

        # Figure out how much space is left for this station.
        free = available_station_space(session, key, station_model,
                                       join_key, max_observations_per_station)
        if free is None:
            is_new_station = True
            free = max_observations_per_station

        if is_new_station:
            # Drop observations for blacklisted stations.
            blacklisted, first_blacklisted = blacklisted_station(
                session, key, blacklist_model, join_key, utcnow)
            if blacklisted:
                dropped_blacklisted += len(observations)
                continue

            incomplete = incomplete_observation(station_type, key)
            if not incomplete:
                # We discovered an actual new complete station.
                new_stations += 1

        # Accept observations up to input-throttling limit, then drop.
        num = 0
        for obs in observations:
            if free <= 0:
                dropped_overflow += 1
                continue
            all_observations.append(obs)
            free -= 1
            num += 1

        # Accept incomplete observations, just don't make stations for them.
        # (station creation is a side effect of count-updating)
        if not incomplete and num > 0:
            create_or_update_station(session, key, station_model,
                                     join_key, utcnow, num,
                                     first_blacklisted)

    # Credit the user with discovering any new stations.
    if userid is not None and new_stations > 0:
        process_score(userid, new_stations, session,
                      key='new_' + station_type)

    if dropped_blacklisted != 0:
        stats_client.incr(
            'items.dropped.%s_ingress_blacklisted' % station_type,
            count=dropped_blacklisted)

    if dropped_malformed != 0:
        stats_client.incr(
            'items.dropped.%s_ingress_malformed' % station_type,
            count=dropped_malformed)

    if dropped_overflow != 0:
        stats_client.incr(
            'items.dropped.%s_ingress_overflow' % station_type,
            count=dropped_overflow)

    stats_client.incr(
        'items.inserted.%s_observations' % station_type,
        count=len(all_observations))

    session.add_all(all_observations)
    return all_observations


@celery.task(base=DatabaseTask, bind=True, queue='celery_incoming')
def insert_measures(self, items=None, nickname='', email='',
                    api_key_log=False, api_key_name=None):
    if not items:  # pragma: no cover
        return 0

    items = kombu_loads(items)
    length = len(items)
    stats_client = self.stats_client

    with self.db_session() as session:
        userid, nickname, email = process_user(nickname, email, session)

        process_observations(items, session,
                             userid=userid,
                             api_key_log=api_key_log,
                             api_key_name=api_key_name)
        stats_client.incr('items.uploaded.reports', length)
        if api_key_log:
            stats_client.incr(
                'items.api_log.%s.uploaded.reports' % api_key_name)

        session.commit()
    return length


@celery.task(base=DatabaseTask, bind=True, queue='celery_insert')
def insert_measures_cell(self, entries, userid=None,
                         max_observations_per_cell=11000,
                         utcnow=None):
    cell_observations = []
    with self.db_session() as session:
        cell_observations = process_station_observations(
            session, entries,
            station_type="cell",
            station_model=Cell,
            observation_model=CellObservation,
            blacklist_model=CellBlacklist,
            create_key=to_cellkey_psc,
            join_key=join_cellkey,
            userid=userid,
            max_observations_per_station=max_observations_per_cell,
            utcnow=utcnow)
        session.commit()
    return len(cell_observations)


@celery.task(base=DatabaseTask, bind=True, queue='celery_insert')
def insert_measures_wifi(self, entries, userid=None,
                         max_observations_per_wifi=11000,
                         utcnow=None):
    wifi_observations = []
    with self.db_session() as session:
        wifi_observations = process_station_observations(
            session, entries,
            station_type="wifi",
            station_model=Wifi,
            observation_model=WifiObservation,
            blacklist_model=WifiBlacklist,
            create_key=to_wifikey,
            join_key=join_wifikey,
            userid=userid,
            max_observations_per_station=max_observations_per_wifi,
            utcnow=utcnow)
        session.commit()
    return len(wifi_observations)


@celery.task(base=DatabaseTask, bind=True)
def location_update_cell(self, min_new=10, max_new=100, batch=10):
    cells = []
    redis_client = self.app.redis_client
    with self.db_session() as session:
        emit_new_observation_metric(self.stats_client, session,
                                    self.shortname, Cell,
                                    min_new, max_new)
        query = (session.query(Cell)
                        .filter(Cell.new_measures >= min_new)
                        .filter(Cell.new_measures < max_new)
                        .limit(batch))
        cells = query.all()
        if not cells:
            return 0
        moving_cells = set()
        updated_lacs = set()
        for cell in cells:
            query = session.query(
                CellObservation.lat,
                CellObservation.lon,
                CellObservation.id).filter(
                    *join_cellkey(CellObservation, cell))
            # only take the last X new_measures
            query = query.order_by(
                CellObservation.created.desc()).limit(
                cell.new_measures)
            observations = query.all()

            if observations:
                moving = calculate_new_position(
                    cell, observations, CELL_MAX_DIST_KM)
                if moving:
                    moving_cells.add(cell)

                updated_lacs.add(
                    CellAreaKey(
                        cell.radio,
                        cell.mcc,
                        cell.mnc,
                        cell.lac))

        if updated_lacs:
            session.on_post_commit(
                enqueue_lacs,
                redis_client,
                updated_lacs,
                UPDATE_KEY['cell_lac'])

        if moving_cells:
            # some cells found to be moving too much
            blacklist_and_remove_moving_cells(session, moving_cells)

        session.commit()

    return (len(cells), len(moving_cells))


@celery.task(base=DatabaseTask, bind=True)
def location_update_wifi(self, min_new=10, max_new=100, batch=10):
    wifis = {}
    with self.db_session() as session:
        emit_new_observation_metric(self.stats_client, session,
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
            observations = session.query(
                WifiObservation.lat, WifiObservation.lon).filter(
                WifiObservation.key == wifi_key).order_by(
                WifiObservation.created.desc()).limit(
                wifi.new_measures).all()
            if observations:
                moving = calculate_new_position(
                    wifi, observations, WIFI_MAX_DIST_KM)
                if moving:
                    moving_wifis.add(wifi)

        if moving_wifis:
            # some wifis found to be moving too much
            blacklist_and_remove_moving_wifis(session, moving_wifis)

        session.commit()
    return (len(wifis), len(moving_wifis))


@celery.task(base=DatabaseTask, bind=True)
def remove_cell(self, cell_keys):
    cells_removed = 0
    redis_client = self.app.redis_client
    with self.db_session() as session:
        changed_lacs = set()

        for k in cell_keys:
            key = to_cellkey(k)
            query = session.query(Cell).filter(*join_cellkey(Cell, key))
            cells_removed += query.delete()
            changed_lacs.add(CellAreaKey(
                radio=key.radio,
                mcc=key.mcc,
                mnc=key.mnc,
                lac=key.lac,
            ))

        if changed_lacs:
            session.on_post_commit(
                enqueue_lacs,
                redis_client,
                changed_lacs,
                UPDATE_KEY['cell_lac'])

        session.commit()
    return cells_removed


@celery.task(base=DatabaseTask, bind=True)
def remove_wifi(self, wifi_keys):
    wifi_keys = set([w['key'] for w in wifi_keys])
    with self.db_session() as session:
        query = session.query(Wifi).filter(
            Wifi.key.in_(wifi_keys))
        wifis = query.delete(synchronize_session=False)
        session.commit()
    return wifis


@celery.task(base=DatabaseTask, bind=True)
def scan_lacs(self, batch=100):
    """
    Find cell LACs that have changed and update the bounding box.
    This includes adding new LAC entries and removing them.
    """
    redis_client = self.app.redis_client
    redis_lacs = dequeue_lacs(
        redis_client, UPDATE_KEY['cell_lac'], batch=batch)
    lacs = set([CellAreaKey(
        radio=lac['radio'],
        mcc=lac['mcc'],
        mnc=lac['mnc'],
        lac=lac['lac'],
    ) for lac in redis_lacs])

    for lac in lacs:
        update_lac.delay(
            lac.radio,
            lac.mcc,
            lac.mnc,
            lac.lac,
            cell_model_key='cell',
            cell_area_model_key='cell_area')
    return len(lacs)


@celery.task(base=DatabaseTask, bind=True)
def update_lac(self, radio, mcc, mnc, lac,
               cell_model_key='cell', cell_area_model_key='cell_area'):
    utcnow = util.utcnow()
    with self.db_session() as session:
        # Select all the cells in this LAC that aren't the virtual
        # cell itself, and derive a bounding box for them.

        cell_model = CELL_MODEL_KEYS[cell_model_key]
        cell_query = (session.query(cell_model)
                             .filter(cell_model.radio == radio)
                             .filter(cell_model.mcc == mcc)
                             .filter(cell_model.mnc == mnc)
                             .filter(cell_model.lac == lac)
                             .filter(cell_model.lat.isnot(None))
                             .filter(cell_model.lon.isnot(None)))

        cells = cell_query.all()

        cell_area_model = CELL_MODEL_KEYS[cell_area_model_key]
        lac_query = (session.query(cell_area_model)
                            .filter(cell_area_model.radio == radio)
                            .filter(cell_area_model.mcc == mcc)
                            .filter(cell_area_model.mnc == mnc)
                            .filter(cell_area_model.lac == lac))

        if len(cells) == 0:
            # If there are no more underlying cells, delete the lac entry
            lac_query.delete()
        else:
            # Otherwise update the lac entry based on all the cells
            lac_obj = lac_query.first()

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
            num_cells = len(cells)
            avg_cell_range = int(sum(
                [cell.range for cell in cells])/float(num_cells))
            if lac_obj is None:
                lac_obj = cell_area_model(
                    created=utcnow,
                    modified=utcnow,
                    radio=radio,
                    mcc=mcc,
                    mnc=mnc,
                    lac=lac,
                    lat=ctr_lat,
                    lon=ctr_lon,
                    range=rng,
                    avg_cell_range=avg_cell_range,
                    num_cells=num_cells,
                )
                session.add(lac_obj)
            else:
                lac_obj.modified = utcnow
                lac_obj.lat = ctr_lat
                lac_obj.lon = ctr_lon
                lac_obj.range = rng
                lac_obj.avg_cell_range = avg_cell_range
                lac_obj.num_cells = num_cells

        session.commit()
