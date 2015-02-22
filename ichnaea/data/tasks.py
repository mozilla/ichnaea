from sqlalchemy.orm import load_only

from ichnaea.async.task import DatabaseTask
from ichnaea.customjson import (
    kombu_dumps,
    kombu_loads,
)
from ichnaea.data.observation import (
    CellObservationQueue,
    WifiObservationQueue,
)
from ichnaea.data.report import ReportQueue
from ichnaea.geocalc import distance, centroid, range_to_points
from ichnaea.logging import get_stats_client
from ichnaea.models import (
    Cell,
    CELL_MODEL_KEYS,
    CellArea,
    CellBlacklist,
    CellObservation,
    Wifi,
    WifiBlacklist,
    WifiObservation,
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


def blacklist_and_remove_moving_stations(session, blacklist_model,
                                         station_type,
                                         moving_stations, remove_station):
    moving_keys = []
    utcnow = util.utcnow()
    for station in moving_stations:
        station_key = blacklist_model.to_hashkey(station)
        query = blacklist_model.querykey(session, station_key)
        blacklisted_station = query.first()
        moving_keys.append(station_key)
        if blacklisted_station:
            blacklisted_station.time = utcnow
            blacklisted_station.count += 1
        else:
            blacklisted_station = blacklist_model(
                time=utcnow,
                count=1,
                **station_key.__dict__)
            session.add(blacklisted_station)

    if moving_keys:
        get_stats_client().incr("items.blacklisted.%s_moving" % station_type,
                                len(moving_keys))
        remove_station.delay(moving_keys)


def blacklist_and_remove_moving_cells(session, moving_cells):
    blacklist_and_remove_moving_stations(session,
                                         blacklist_model=CellBlacklist,
                                         station_type="cell",
                                         moving_stations=moving_cells,
                                         remove_station=remove_cell)


def blacklist_and_remove_moving_wifis(session, moving_wifis):
    blacklist_and_remove_moving_stations(session,
                                         blacklist_model=WifiBlacklist,
                                         station_type="wifi",
                                         moving_stations=moving_wifis,
                                         remove_station=remove_wifi)


def calculate_new_position(station, observations, max_dist_km):
    # This function returns True if the station was found to be moving.
    length = len(observations)
    latitudes = [obs.lat for obs in observations]
    longitudes = [obs.lon for obs in observations]
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


def emit_new_observation_metric(stats_client, session, shortname,
                                model, min_new, max_new):
    q = session.query(model).filter(
        model.new_measures >= min_new,
        model.new_measures < max_new)
    n = q.count()
    stats_client.gauge('task.%s.new_measures_%d_%d' %
                       (shortname, min_new, max_new), n)


@celery.task(base=DatabaseTask, bind=True, queue='celery_incoming')
def insert_measures(self, items=None, nickname='', email='',
                    api_key_log=False, api_key_name=None):
    if not items:  # pragma: no cover
        return 0

    reports = kombu_loads(items)
    with self.db_session() as session:
        queue = ReportQueue(self, session,
                            api_key_log=api_key_log,
                            api_key_name=api_key_name,
                            insert_cell_task=insert_measures_cell,
                            insert_wifi_task=insert_measures_wifi)
        length = queue.insert(reports, nickname=nickname, email=email)
        session.commit()
    return length


@celery.task(base=DatabaseTask, bind=True, queue='celery_insert')
def insert_measures_cell(self, entries, userid=None,
                         max_observations_per_cell=11000,
                         utcnow=None):

    with self.db_session() as session:
        queue = CellObservationQueue(
            self, session, utcnow=utcnow,
            max_observations=max_observations_per_cell)
        length = queue.insert(entries, userid=userid)
        session.commit()
    return length


@celery.task(base=DatabaseTask, bind=True, queue='celery_insert')
def insert_measures_wifi(self, entries, userid=None,
                         max_observations_per_wifi=11000,
                         utcnow=None):

    with self.db_session() as session:
        queue = WifiObservationQueue(
            self, session, utcnow=utcnow,
            max_observations=max_observations_per_wifi)
        length = queue.insert(entries, userid=userid)
        session.commit()
    return length


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
            # only take the last X new_measures
            query = (CellObservation.querykey(session, cell)
                                    .options(load_only('lat', 'lon'))
                                    .order_by(CellObservation.created.desc())
                                    .limit(cell.new_measures))
            observations = query.all()

            if observations:
                moving = calculate_new_position(
                    cell, observations, CELL_MAX_DIST_KM)
                if moving:
                    moving_cells.add(cell)

                updated_lacs.add(CellArea.to_hashkey(cell))

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
        query = session.query(Wifi).filter(
            Wifi.new_measures >= min_new).filter(
            Wifi.new_measures < max_new).limit(batch)
        wifis = query.all()
        if not wifis:
            return 0
        moving_wifis = set()
        for wifi in wifis:
            # only take the last X new_measures
            query = (WifiObservation.querykey(session, wifi)
                                    .options(load_only('lat', 'lon'))
                                    .order_by(WifiObservation.created.desc())
                                    .limit(wifi.new_measures))
            observations = query.all()

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

        for key in cell_keys:
            query = Cell.querykey(session, key)
            cells_removed += query.delete()
            changed_lacs.add(CellArea.to_hashkey(key))

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
    # BBB this might still get namedtuples encoded as a dicts for
    # one release, afterwards it'll get wifi hashkeys
    keys = [Wifi.to_hashkey(key=wifi['key']) for wifi in wifi_keys]
    with self.db_session() as session:
        query = Wifi.querykeys(session, keys)
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
    lacs = set([CellArea.to_hashkey(lac) for lac in redis_lacs])

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
