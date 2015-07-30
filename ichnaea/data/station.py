from collections import defaultdict

from ichnaea.constants import (
    PERMANENT_BLOCKLIST_THRESHOLD,
    TEMPORARY_BLOCKLIST_DURATION,
)
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
    StatCounter,
    StatKey,
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
        self.utcnow = util.utcnow()

    def stat_count(self, action, count, reason=None):
        if count != 0:
            tags = ['type:%s' % self.station_type]
            if reason:
                tags.append('reason:%s' % reason)
            self.stats_client.incr(
                'data.observation.%s' % action,
                count,
                tags=tags)

    def emit_stats(self, added, dropped):
        self.stat_count('insert', added)
        for reason, count in dropped.items():
            self.stat_count('drop', dropped[reason], reason=reason)

    def emit_statcounters(self, obs, stations):
        day = self.utcnow.date()
        StatCounter(self.stat_obs_key, day).incr(self.pipe, obs)
        StatCounter(self.stat_station_key, day).incr(self.pipe, stations)

    def create_or_update_station(self, station, station_key,
                                 first_blocked, observations):
        # This function returns True if the station was found to be moving.
        length = len(observations)
        latitudes = [obs.lat for obs in observations]
        longitudes = [obs.lon for obs in observations]
        new_lat = sum(latitudes) / length
        new_lon = sum(longitudes) / length

        values = {
            'modified': self.utcnow,
        }
        if self.station_type == 'cell':
            # pass on extra psc column which is not actually part
            # of the stations hash key
            values['psc'] = observations[-1].psc

        created = self.utcnow
        if station is None:
            if first_blocked:
                # if the station did previously exist, retain at least the
                # time it was first put on a blocklist as the creation date
                created = first_blocked
            values.update({
                'created': created,
                'range': 0,
                'total_measures': 0,
            })
            values.update(station_key.__dict__)

        if station is not None and station.lat and station.lon:
            latitudes.append(station.lat)
            longitudes.append(station.lon)
            existing_station = True
        else:
            values['lat'] = new_lat
            values['lon'] = new_lon
            existing_station = False

        # calculate extremes of observations, existing location estimate
        # and existing extreme values
        def extreme(vals, attr, function):
            new = function(vals)
            if station is not None:
                old = getattr(station, attr, None)
            else:
                old = None
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

        # TODO: If we get a too large box_dist, we should not create
        # a new station record with the impossibly big distance,
        # so moving the box_dist > self.max_dist_km here

        if existing_station:
            if box_dist > self.max_dist_km:
                # Signal a moving station and return early without updating
                # the station since it will be deleted by caller momentarily
                return True
            # limit the maximum weight of the old station estimate
            old_weight = min(station.total_measures,
                             self.MAX_OLD_OBSERVATIONS)
            new_weight = old_weight + length

            values['lat'] = ((station.lat * old_weight) +
                             (new_lat * length)) / new_weight
            values['lon'] = ((station.lon * old_weight) +
                             (new_lon * length)) / new_weight

        # increase total counter, new isn't used
        if station is not None:
            values['total_measures'] = station.total_measures + length
        else:
            values['total_measures'] = length

        # update max/min lat/lon columns
        values['min_lat'] = min_lat
        values['min_lon'] = min_lon
        values['max_lat'] = max_lat
        values['max_lon'] = max_lon

        # give radio-range estimate between extreme values and centroid
        ctr = (values['lat'], values['lon'])
        points = [(min_lat, min_lon),
                  (min_lat, max_lon),
                  (max_lat, min_lon),
                  (max_lat, max_lon)]

        values['range'] = range_to_points(ctr, points) * 1000.0

        if station is None:
            stmt = self.station_model.__table__.insert(
                on_duplicate='total_measures = total_measures'  # no-op change
            ).values(**values)
            self.session.execute(stmt)
        else:
            for key, value in values.items():
                setattr(station, key, value)
        return False

    def blocklisted_station(self, block):
        age = self.utcnow - block.time
        temporary = age < TEMPORARY_BLOCKLIST_DURATION
        permanent = block.count >= PERMANENT_BLOCKLIST_THRESHOLD
        if temporary or permanent:
            return (True, block.time, block)
        return (False, block.time, block)

    def blocklist_stations(self, moving):
        moving_keys = []
        for station_key, block in moving:
            block_key = self.blocklist_model.to_hashkey(station_key)
            moving_keys.append(block_key)
            if block:
                block.time = self.utcnow
                block.count += 1
            else:
                block = self.blocklist_model(
                    time=self.utcnow,
                    count=1,
                    **block_key.__dict__)
                self.session.add(block)

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
        drop_counter = defaultdict(int)
        added = 0
        new_stations = 0
        station_obs = defaultdict(list)

        for obs in all_observations:
            station_obs[self.station_model.to_hashkey(obs)].append(obs)

        if not station_obs:
            return (0, 0)

        stations = {}
        for station in self.station_model.iterkeys(self.session,
                                                   list(station_obs.keys())):
            stations[station.hashkey()] = station

        blocklist = {}
        for block in self.blocklist_model.iterkeys(self.session,
                                                   list(station_obs.keys())):
            blocklist[block.hashkey()] = self.blocklisted_station(block)

        moving_stations = set()
        for station_key, observations in station_obs.items():
            blocked, first_blocked, block = blocklist.get(
                station_key, (False, None, None))

            if not any(observations):
                continue

            if blocked:
                # Drop observations for blocklisted stations.
                drop_counter['blocklisted'] += len(observations)
                continue

            station = stations.get(station_key, None)
            if station is None and not first_blocked:
                # We discovered an actual new never before seen station.
                new_stations += 1

            moving = self.create_or_update_station(
                station, station_key, first_blocked, observations)
            if moving:
                moving_stations.add((station_key, block))
            else:
                added += len(observations)
                if station is None:
                    # make the return counter happy
                    stations[station_key] = True

            # track potential updates to dependent areas
            self.add_area_update(station_key)

        self.queue_area_updates()

        if moving_stations:
            self.blocklist_stations(moving_stations)

        self.emit_stats(added, drop_counter)
        self.emit_statcounters(added, new_stations)

        if self.data_queue.enough_data(batch=batch):  # pragma: no cover
            self.update_task.apply_async(
                kwargs={'batch': batch},
                countdown=2,
                expires=10)

        return (len(stations), len(moving_stations))

    def add_area_update(self, station_key):
        pass

    def queue_area_updates(self):
        pass


class CellUpdater(StationUpdater):

    blocklist_model = CellBlocklist
    max_dist_km = 150
    observation_model = CellObservation
    queue_name = 'update_cell'
    stat_obs_key = StatKey.cell
    stat_station_key = StatKey.unique_cell
    station_model = Cell
    station_type = 'cell'

    def add_area_update(self, station_key):
        area_key = CellArea.to_hashkey(station_key)
        self.updated_areas.add(area_key)

    def queue_area_updates(self):
        if self.updated_areas:
            data_queue = self.task.app.data_queues['update_cellarea']
            data_queue.enqueue(self.updated_areas, pipe=self.pipe)


class WifiUpdater(StationUpdater):

    blocklist_model = WifiBlocklist
    max_dist_km = 5
    observation_model = WifiObservation
    queue_name = 'update_wifi'
    stat_obs_key = StatKey.wifi
    stat_station_key = StatKey.unique_wifi
    station_model = Wifi
    station_type = 'wifi'
