from collections import defaultdict

from ichnaea.data.base import DataTask
from ichnaea.geocalc import (
    distance,
    range_to_points,
)
from ichnaea.models import (
    Cell,
    CellArea,
    CellBlocklist,
    CellObservation,
    Wifi,
    WifiBlocklist,
    WifiObservation,
)
from ichnaea import util


class StationRemover(DataTask):

    def __init__(self, task, session, pipe):
        DataTask.__init__(self, task, session)
        self.pipe = pipe


class CellRemover(StationRemover):

    def remove(self, cell_keys):
        cells_removed = 0
        changed_areas = set()
        data_queue = self.task.app.data_queues['update_cellarea']

        for key in cell_keys:
            query = Cell.querykey(self.session, key)
            cells_removed += query.delete()
            changed_areas.add(CellArea.to_hashkey(key))

        if changed_areas:
            data_queue.enqueue(changed_areas, pipe=self.pipe)

        return cells_removed


class WifiRemover(StationRemover):

    def remove(self, wifi_keys):
        query = Wifi.querykeys(self.session, wifi_keys)
        length = query.delete(synchronize_session=False)
        return length


class StationUpdater(DataTask):

    MAX_OLD_OBSERVATIONS = 1000

    def __init__(self, task, session, pipe,
                 remove_task=None, update_task=None):
        DataTask.__init__(self, task, session)
        self.pipe = pipe
        self.remove_task = remove_task
        self.updated_areas = set()
        self.update_task = update_task
        self.data_queue = self.task.app.data_queues[self.queue_name]

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

            # limit the maximum weight of the old station estimate
            old_weight = min(station.total_measures,
                             self.MAX_OLD_OBSERVATIONS)
            new_weight = old_weight + length

            station.lat = ((station.lat * old_weight) +
                           (new_lat * length)) / new_weight
            station.lon = ((station.lon * old_weight) +
                           (new_lon * length)) / new_weight

        # increase total counter, new isn't used
        station.total_measures = station.total_measures + length

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

    def blocklist_stations(self, stations):
        moving_keys = []
        utcnow = util.utcnow()
        for station in stations:
            station_key = self.blocklist_model.to_hashkey(station)
            query = self.blocklist_model.querykey(self.session, station_key)
            blocked = query.first()
            moving_keys.append(station_key)
            if blocked:
                blocked.time = utcnow
                blocked.count += 1
            else:
                blocked = self.blocklist_model(
                    time=utcnow,
                    count=1,
                    **station_key.__dict__)
                self.session.add(blocked)

        if moving_keys:
            self.stats_client.incr(
                'data.station.blocklist',
                len(moving_keys),
                tags=['type:%s' % self.station_type,
                      'action:add',
                      'reason:moving'])
            self.remove_task.delay(moving_keys)

    def update(self, batch=10):
        all_observations = self.data_queue.dequeue(batch=batch)
        station_obs = defaultdict(list)

        for obs in all_observations:
            station_obs[self.station_model.to_hashkey(obs)].append(obs)

        if not station_obs:
            return (0, 0)

        stations = list(self.station_model.iterkeys(
            self.session, list(station_obs.keys())))

        if not stations:  # pragma: no cover
            # TODO: This task depends on the station records to be
            # pre-created, move that logic into this task later on.
            return (0, 0)

        moving_stations = set()
        for station in stations:
            observations = station_obs.get(station.hashkey())
            if observations:
                moving = self.calculate_new_position(station, observations)
                if moving:
                    moving_stations.add(station)

                # track potential updates to dependent areas
                self.add_area_update(station)

        self.queue_area_updates()

        if moving_stations:
            self.blocklist_stations(moving_stations)

        if self.data_queue.enough_data(batch=batch):  # pragma: no cover
            self.update_task.apply_async(
                kwargs={'batch': batch},
                countdown=2,
                expires=10)

        return (len(stations), len(moving_stations))

    def add_area_update(self, station):
        pass

    def queue_area_updates(self):
        pass


class CellUpdater(StationUpdater):

    blocklist_model = CellBlocklist
    max_dist_km = 150
    observation_model = CellObservation
    queue_name = 'update_cell'
    station_model = Cell
    station_type = 'cell'

    def add_area_update(self, station):
        self.updated_areas.add(CellArea.to_hashkey(station))

    def queue_area_updates(self):
        if self.updated_areas:
            data_queue = self.task.app.data_queues['update_cellarea']
            data_queue.enqueue(self.updated_areas, pipe=self.pipe)


class WifiUpdater(StationUpdater):

    blocklist_model = WifiBlocklist
    max_dist_km = 5
    observation_model = WifiObservation
    queue_name = 'update_wifi'
    station_model = Wifi
    station_type = 'wifi'
