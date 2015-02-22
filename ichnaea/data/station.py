from sqlalchemy.orm import load_only

from ichnaea.data.area import (
    enqueue_lacs,
    UPDATE_KEY,
)
from ichnaea.data.base import DataTask
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


class StationRemover(DataTask):

    def __init__(self, task, session):
        DataTask.__init__(self, task, session)


class CellRemover(StationRemover):

    def remove(self, cell_keys):
        cells_removed = 0
        changed_areas = set()

        for key in cell_keys:
            query = Cell.querykey(self.session, key)
            cells_removed += query.delete()
            changed_areas.add(CellArea.to_hashkey(key))

        if changed_areas:
            self.session.on_post_commit(
                enqueue_lacs,
                self.redis_client,
                changed_areas,
                UPDATE_KEY['cell_lac'])

        return cells_removed


class WifiRemover(StationRemover):

    def remove(self, wifi_keys):
        # BBB this might still get namedtuples encoded as a dicts for
        # one release, afterwards it'll get wifi hashkeys
        keys = [Wifi.to_hashkey(key=wifi['key']) for wifi in wifi_keys]
        query = Wifi.querykeys(self.session, keys)
        length = query.delete(synchronize_session=False)
        return length


class StationUpdater(DataTask):

    def __init__(self, task, session,
                 min_new=10, max_new=100, remove_task=None):
        DataTask.__init__(self, task, session)
        self.min_new = min_new
        self.max_new = max_new
        self.remove_task = remove_task

    def emit_new_observation_metric(self):
        num = self.station_query().count()
        self.stats_client.gauge(
            'task.%s.new_measures_%d_%d' % (
                self.task_shortname, self.min_new, self.max_new),
            num)

    def station_query(self):
        model = self.station_model
        query = (self.session.query(model)
                             .filter(model.new_measures >= self.min_new)
                             .filter(model.new_measures < self.max_new))
        return query

    def observation_query(self, station):
        # only take the last X new_measures
        model = self.observation_model
        query = (model.querykey(self.session, station)
                      .options(load_only('lat', 'lon'))
                      .order_by(model.created.desc())
                      .limit(station.new_measures))
        return query

    def calculate_new_position(self, station, observations):
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

            if box_dist > self.max_dist_km:
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

    def blacklist_stations(self, stations):
        moving_keys = []
        utcnow = util.utcnow()
        for station in stations:
            station_key = self.blacklist_model.to_hashkey(station)
            query = self.blacklist_model.querykey(self.session, station_key)
            blacklisted_station = query.first()
            moving_keys.append(station_key)
            if blacklisted_station:
                blacklisted_station.time = utcnow
                blacklisted_station.count += 1
            else:
                blacklisted_station = self.blacklist_model(
                    time=utcnow,
                    count=1,
                    **station_key.__dict__)
                self.session.add(blacklisted_station)

        if moving_keys:
            self.stats_client.incr(
                "items.blacklisted.%s_moving" % self.station_type,
                len(moving_keys))
            self.remove_task.delay(moving_keys)

    def update(self, batch=10):
        moving_stations = set()
        updated_areas = set()

        self.emit_new_observation_metric()

        stations = self.station_query().limit(batch).all()
        if not stations:
            return (0, 0)

        for station in stations:
            observations = self.observation_query(station).all()
            if observations:
                moving = self.calculate_new_position(station, observations)
                if moving:
                    moving_stations.add(station)

                if self.area_model:
                    updated_areas.add(self.area_model.to_hashkey(station))

        if updated_areas and self.area_enqueue:
            self.session.on_post_commit(
                self.area_enqueue,
                self.redis_client,
                updated_areas,
                self.area_update_key)

        if moving_stations:
            self.blacklist_stations(moving_stations)

        return (len(stations), len(moving_stations))


class CellUpdater(StationUpdater):

    area_model = CellArea
    area_enqueue = staticmethod(enqueue_lacs)
    area_update_key = UPDATE_KEY['cell_lac']
    blacklist_model = CellBlacklist
    max_dist_km = 150
    observation_model = CellObservation
    station_model = Cell
    station_type = 'cell'


class WifiUpdater(StationUpdater):

    area_model = None
    area_enqueue = None
    area_update_key = None
    blacklist_model = WifiBlacklist
    max_dist_km = 5
    observation_model = WifiObservation
    station_model = Wifi
    station_type = 'wifi'
