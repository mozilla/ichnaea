from sqlalchemy.orm import load_only

from ichnaea.customjson import (
    kombu_dumps,
    kombu_loads,
)
from ichnaea.geocalc import (
    distance,
    range_to_points,
)
from ichnaea.models import (
    Cell,
    CellArea,
    CellBlacklist,
    CellObservation,
    Wifi,
    WifiBlacklist,
    WifiObservation,
)
from ichnaea import util

CELL_MAX_DIST_KM = 150
WIFI_MAX_DIST_KM = 5

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


class StationUpdater(object):

    def __init__(self, task, session, remove_task=None):
        self.task = task
        self.session = session
        self.remove_task = remove_task
        self.shortname = task.shortname
        self.redis_client = task.app.redis_client
        self.stats_client = task.stats_client

    def emit_new_observation_metric(self, shortname,
                                    model, min_new, max_new):
        q = self.session.query(model).filter(
            model.new_measures >= min_new,
            model.new_measures < max_new)
        n = q.count()
        self.stats_client.gauge('task.%s.new_measures_%d_%d' %
                                (shortname, min_new, max_new), n)

    def calculate_new_position(self, station, observations, max_dist_km):
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

    def blacklist_and_remove_moving_stations(self, blacklist_model,
                                             station_type,
                                             moving_stations, remove_station):
        moving_keys = []
        utcnow = util.utcnow()
        for station in moving_stations:
            station_key = blacklist_model.to_hashkey(station)
            query = blacklist_model.querykey(self.session, station_key)
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
                self.session.add(blacklisted_station)

        if moving_keys:
            self.stats_client.incr(
                "items.blacklisted.%s_moving" % station_type, len(moving_keys))
            remove_station.delay(moving_keys)


class CellStationUpdater(StationUpdater):

    def update(self, min_new=10, max_new=100, batch=10):
        cells = []
        moving_cells = set()
        updated_lacs = set()

        self.emit_new_observation_metric(self.shortname, Cell,
                                         min_new, max_new)
        query = (self.session.query(Cell)
                             .filter(Cell.new_measures >= min_new)
                             .filter(Cell.new_measures < max_new)
                             .limit(batch))
        cells = query.all()
        if not cells:
            return (0, 0)

        for cell in cells:
            # only take the last X new_measures
            query = (CellObservation.querykey(self.session, cell)
                                    .options(load_only('lat', 'lon'))
                                    .order_by(CellObservation.created.desc())
                                    .limit(cell.new_measures))
            observations = query.all()

            if observations:
                moving = self.calculate_new_position(
                    cell, observations, CELL_MAX_DIST_KM)
                if moving:
                    moving_cells.add(cell)

                updated_lacs.add(CellArea.to_hashkey(cell))

        if updated_lacs:
            self.session.on_post_commit(
                enqueue_lacs,
                self.redis_client,
                updated_lacs,
                UPDATE_KEY['cell_lac'])

        if moving_cells:
            # some cells found to be moving too much
            self.blacklist_and_remove_moving_cells(moving_cells)

        return (len(cells), len(moving_cells))

    def blacklist_and_remove_moving_cells(self, moving_cells):
        self.blacklist_and_remove_moving_stations(
            blacklist_model=CellBlacklist,
            station_type="cell",
            moving_stations=moving_cells,
            remove_station=self.remove_task)


class WifiStationUpdater(StationUpdater):

    def update(self, min_new=10, max_new=100, batch=10):
        wifis = {}
        moving_wifis = set()

        self.emit_new_observation_metric(self.shortname, Wifi,
                                         min_new, max_new)
        query = self.session.query(Wifi).filter(
            Wifi.new_measures >= min_new).filter(
            Wifi.new_measures < max_new).limit(batch)
        wifis = query.all()
        if not wifis:
            return (0, 0)

        for wifi in wifis:
            # only take the last X new_measures
            query = (WifiObservation.querykey(self.session, wifi)
                                    .options(load_only('lat', 'lon'))
                                    .order_by(WifiObservation.created.desc())
                                    .limit(wifi.new_measures))
            observations = query.all()

            if observations:
                moving = self.calculate_new_position(
                    wifi, observations, WIFI_MAX_DIST_KM)
                if moving:
                    moving_wifis.add(wifi)

        if moving_wifis:
            # some wifis found to be moving too much
            self.blacklist_and_remove_moving_wifis(moving_wifis)

        return (len(wifis), len(moving_wifis))

    def blacklist_and_remove_moving_wifis(self, moving_wifis):
        self.blacklist_and_remove_moving_stations(
            blacklist_model=WifiBlacklist,
            station_type="wifi",
            moving_stations=moving_wifis,
            remove_station=self.remove_task)
