from collections import defaultdict

import numpy

from ichnaea.constants import (
    PERMANENT_BLOCKLIST_THRESHOLD,
    TEMPORARY_BLOCKLIST_DURATION,
)
from ichnaea.data.base import DataTask
from ichnaea.geocalc import (
    centroid,
    circle_radius,
    country_for_location,
    distance,
)
from ichnaea.models import (
    Cell,
    CellArea,
    CellBlocklist,
    StatCounter,
    StatKey,
    WifiShard,
)
from ichnaea import util


class CellRemover(DataTask):

    def __init__(self, task, session, pipe):
        super(CellRemover, self).__init__(task, session)
        self.pipe = pipe

    def __call__(self, cell_keys):
        cells_removed = 0
        changed_areas = set()
        area_queue = self.task.app.data_queues['update_cellarea']

        for key in cell_keys:
            query = Cell.querykey(self.session, key)
            cells_removed += query.delete()
            changed_areas.add(CellArea.to_hashkey(key))

        if changed_areas:
            area_queue.enqueue(changed_areas, pipe=self.pipe)

        return cells_removed


class StationUpdater(DataTask):

    MAX_OLD_OBSERVATIONS = 1000
    max_dist_meters = None
    queue_name = None
    station_type = None

    def __init__(self, task, session, pipe,
                 remove_task=None, update_task=None):
        super(StationUpdater, self).__init__(task, session)
        self.pipe = pipe
        self.remove_task = remove_task
        self.updated_areas = set()
        self.update_task = update_task
        self.data_queue = self.task.app.data_queues[self.queue_name]
        self.utcnow = util.utcnow()
        self.today = self.utcnow.date()

    def stat_count(self, action, count, reason=None):
        if count > 0:
            tags = ['type:%s' % self.station_type]
            if reason:
                tags.append('reason:%s' % reason)
            self.stats_client.incr(
                'data.observation.%s' % action,
                count,
                tags=tags)

    def __call__(self, batch=10):
        raise NotImplementedError()


class CellUpdater(StationUpdater):

    max_dist_meters = 150000
    queue_name = 'update_cell'
    station_type = 'cell'

    def emit_statcounters(self, obs, stations):
        day = self.today
        StatCounter(StatKey.cell, day).incr(self.pipe, obs)
        StatCounter(StatKey.unique_cell, day).incr(self.pipe, stations)

    def emit_stats(self, added, dropped):
        self.stat_count('insert', added)
        for reason, count in dropped.items():
            self.stat_count('drop', dropped[reason], reason=reason)

    def add_area_update(self, station_key):
        area_key = CellArea.to_hashkey(station_key)
        self.updated_areas.add(area_key)

    def queue_area_updates(self):
        data_queue = self.task.app.data_queues['update_cellarea']
        data_queue.enqueue(self.updated_areas, pipe=self.pipe)

    def blocklisted_station(self, block):
        age = self.utcnow - block.time
        temporary = age < TEMPORARY_BLOCKLIST_DURATION
        permanent = block.count >= PERMANENT_BLOCKLIST_THRESHOLD
        if temporary or permanent:
            return (True, block.time, block)
        return (False, block.time, block)

    def blocklisted_stations(self, station_keys):
        blocklist = {}
        for block in CellBlocklist.iterkeys(
                self.session, list(station_keys)):
            blocklist[block.hashkey()] = self.blocklisted_station(block)
        return blocklist

    def blocklist_stations(self, moving):
        moving_keys = []
        new_block_values = []
        for station_key, block in moving:
            moving_keys.append(station_key)
            if block:
                block.time = self.utcnow
                block.count += 1
            else:
                block_key = CellBlocklist.to_hashkey(station_key)
                new_block_values.append(dict(
                    time=self.utcnow,
                    count=1,
                    **block_key.__dict__
                ))
        if new_block_values:
            # do a batch insert of new blocks
            stmt = CellBlocklist.__table__.insert(
                mysql_on_duplicate='time = time'  # no-op
            )
            # but limit the batch depending on each model
            ins_batch = CellBlocklist._insert_batch
            for i in range(0, len(new_block_values), ins_batch):
                batch_values = new_block_values[i:i + ins_batch]
                self.session.execute(stmt.values(batch_values))

        if moving_keys:
            self.stats_client.incr(
                'data.station.blocklist',
                len(moving_keys),
                tags=['type:%s' % self.station_type,
                      'action:add',
                      'reason:moving'])
            self.remove_task.delay(moving_keys)

    def new_station_values(self, station, station_key,
                           first_blocked, observations):
        # This function returns a 3-tuple, the first element is True,
        # if the station was found to be moving.
        # The second element is either None or a dict of values,
        # if the station is new and should result in a table insert
        # The third element is either None or a dict of values
        # if the station did exist and should be updated

        obs_length = len(observations)
        obs_positions = numpy.array(
            [(obs.lat, obs.lon) for obs in observations],
            dtype=numpy.double)
        obs_lat, obs_lon = centroid(obs_positions)

        values = {
            'modified': self.utcnow,
        }
        values.update(station_key.__dict__)
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

        if (station is not None and
                station.lat is not None and station.lon is not None):
            obs_positions = numpy.append(obs_positions, [
                (station.lat, station.lon),
                (numpy.nan if station.max_lat is None else station.max_lat,
                 numpy.nan if station.max_lon is None else station.max_lon),
                (numpy.nan if station.min_lat is None else station.min_lat,
                 numpy.nan if station.min_lon is None else station.min_lon),
            ], axis=0)
            existing_station = True
        else:
            values['lat'] = obs_lat
            values['lon'] = obs_lon
            existing_station = False

        max_lat, max_lon = numpy.nanmax(obs_positions, axis=0)
        min_lat, min_lon = numpy.nanmin(obs_positions, axis=0)

        # calculate sphere-distance from opposite corners of
        # bounding box containing current location estimate
        # and new observations; if too big, station is moving
        box_dist = distance(min_lat, min_lon, max_lat, max_lon)

        # TODO: If we get a too large box_dist, we should not create
        # a new station record with the impossibly big distance,
        # so moving the box_dist > self.max_dist_meters here

        if existing_station:
            if box_dist > self.max_dist_meters:
                # Signal a moving station and return early without updating
                # the station since it will be deleted by caller momentarily
                return (True, None, None)
            # limit the maximum weight of the old station estimate
            old_weight = min(station.total_measures,
                             self.MAX_OLD_OBSERVATIONS)
            new_weight = old_weight + obs_length

            values['lat'] = ((station.lat * old_weight) +
                             (obs_lat * obs_length)) / new_weight
            values['lon'] = ((station.lon * old_weight) +
                             (obs_lon * obs_length)) / new_weight

        # increase total counter
        if station is not None:
            values['total_measures'] = station.total_measures + obs_length
        else:
            values['total_measures'] = obs_length

        # update max/min lat/lon columns
        values['min_lat'] = float(min_lat)
        values['min_lon'] = float(min_lon)
        values['max_lat'] = float(max_lat)
        values['max_lon'] = float(max_lon)

        # give radio-range estimate between extreme values and centroid
        values['range'] = circle_radius(
            values['lat'], values['lon'],
            max_lat, max_lon, min_lat, min_lon)

        if station is None:
            # return new values
            return (False, values, None)
        else:
            # return updated values, remove station from session
            self.session.expunge(station)
            return (False, None, values)

    def __call__(self, batch=10):
        all_observations = self.data_queue.dequeue(batch=batch)
        drop_counter = defaultdict(int)
        added = 0
        new_stations = 0
        station_obs = defaultdict(list)

        for obs in all_observations:
            station_obs[Cell.to_hashkey(obs)].append(obs)

        if not station_obs:
            return (0, 0)

        stations = {}
        for station in Cell.iterkeys(self.session, list(station_obs.keys())):
            stations[station.hashkey()] = station

        blocklist = self.blocklisted_stations(station_obs.keys())

        new_station_values = []
        changed_station_values = []
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

            moving, new_values, changed_values = self.new_station_values(
                station, station_key, first_blocked, observations)
            if moving:
                moving_stations.add((station_key, block))
            else:
                added += len(observations)
                if new_values:
                    new_station_values.append(new_values)
                if changed_values:
                    changed_station_values.append(changed_values)

            # track potential updates to dependent areas
            self.add_area_update(station_key)

        if new_station_values:
            # do a batch insert of new stations
            stmt = Cell.__table__.insert(
                mysql_on_duplicate='total_measures = total_measures'  # no-op
            )
            # but limit the batch depending on each model
            ins_batch = Cell._insert_batch
            for i in range(0, len(new_station_values), ins_batch):
                batch_values = new_station_values[i:i + ins_batch]
                self.session.execute(stmt.values(batch_values))

        if changed_station_values:
            # do a batch update of changed stations
            ins_batch = Cell._insert_batch
            for i in range(0, len(changed_station_values), ins_batch):
                batch_values = changed_station_values[i:i + ins_batch]
                self.session.bulk_update_mappings(Cell, batch_values)

        if self.updated_areas:
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

        return (len(stations) + len(new_station_values), len(moving_stations))


class WifiUpdater(StationUpdater):

    max_dist_meters = 5000
    queue_name = 'update_wifi'
    station_type = 'wifi'

    def emit_stats(self, stats_counter, drop_counter):
        day = self.today
        StatCounter(StatKey.wifi, day).incr(
            self.pipe, stats_counter['obs'])
        StatCounter(StatKey.unique_wifi, day).incr(
            self.pipe, stats_counter['new_station'])

        self.stat_count('insert', stats_counter['obs'])
        for reason, count in drop_counter.items():
            self.stat_count('drop', drop_counter[reason], reason=reason)
        if stats_counter['block']:
            self.stats_client.incr(
                'data.station.blocklist',
                stats_counter['block'],
                tags=['type:%s' % self.station_type,
                      'action:add',
                      'reason:moving'])

    def station_values(self, station_key, shard_station, observations):
        """
        Return two-tuple of status, value dict where status is one of:
        `new`, `new_moving`, `moving`, `changed`.
        """
        # cases:
        # we always get a station key and observations
        # 0. observations disagree
        # 0.a. no shard station, return new_moving
        # 0.b. shard station, return moving
        # 1. no shard station
        # 1.a. obs agree -> return new
        # 2. shard station
        # 2.a. obs disagree -> return moving
        # 2.b. obs agree -> return changed
        created = self.utcnow
        values = {
            'mac': station_key,
            'modified': self.utcnow,
        }

        obs_length = len(observations)
        obs_positions = numpy.array(
            [(obs.lat, obs.lon) for obs in observations],
            dtype=numpy.double)
        obs_new_lat, obs_new_lon = centroid(obs_positions)
        obs_max_lat, obs_max_lon = numpy.nanmax(obs_positions, axis=0)
        obs_min_lat, obs_min_lon = numpy.nanmin(obs_positions, axis=0)
        obs_box_dist = distance(obs_min_lat, obs_min_lon,
                                obs_max_lat, obs_max_lon)

        if obs_box_dist > self.max_dist_meters:
            # the new observations are already too far apart
            if not shard_station:
                values.update({
                    'created': created,
                    'block_first': self.today,
                    'block_last': self.today,
                    'block_count': 1,
                })
                return ('new_moving', values)
            else:
                block_count = shard_station.block_count or 0
                values.update({
                    'lat': None,
                    'lon': None,
                    'max_lat': None,
                    'min_lat': None,
                    'max_lon': None,
                    'min_lon': None,
                    'country': shard_station.country,
                    'radius': None,
                    'samples': None,
                    'source': None,
                    'block_last': self.today,
                    'block_count': block_count + 1,
                })
                return ('moving', values)

        if shard_station is None:
            # totally new station, only agreeing observations
            radius = circle_radius(
                obs_new_lat, obs_new_lon,
                obs_max_lat, obs_max_lon, obs_min_lat, obs_min_lon)
            values.update({
                'created': created,
                'lat': obs_new_lat,
                'lon': obs_new_lon,
                'max_lat': float(obs_max_lat),
                'min_lat': float(obs_min_lat),
                'max_lon': float(obs_max_lon),
                'min_lon': float(obs_min_lon),
                'country': country_for_location(obs_new_lat, obs_new_lon),
                'radius': radius,
                'samples': obs_length,
                'source': None,
            })
            return ('new', values)
        else:
            # shard_station + new observations
            positions = numpy.append(obs_positions, [
                (numpy.nan if shard_station.lat is None
                    else shard_station.lat,
                 numpy.nan if shard_station.lon is None
                    else shard_station.lon),
                (numpy.nan if shard_station.max_lat is None
                    else shard_station.max_lat,
                 numpy.nan if shard_station.max_lon is None
                    else shard_station.max_lon),
                (numpy.nan if shard_station.min_lat is None
                    else shard_station.min_lat,
                 numpy.nan if shard_station.min_lon is None
                    else shard_station.min_lon),
            ], axis=0)
            max_lat, max_lon = numpy.nanmax(positions, axis=0)
            min_lat, min_lon = numpy.nanmin(positions, axis=0)
            box_dist = distance(min_lat, min_lon, max_lat, max_lon)
            if box_dist > self.max_dist_meters:
                # shard_station + disagreeing observations
                block_count = shard_station.block_count or 0
                values.update({
                    'lat': None,
                    'lon': None,
                    'max_lat': None,
                    'min_lat': None,
                    'max_lon': None,
                    'min_lon': None,
                    'country': shard_station.country,
                    'radius': None,
                    'samples': None,
                    'source': None,
                    'block_last': self.today,
                    'block_count': block_count + 1,
                })
                return ('moving', values)
            else:
                # shard_station + agreeing observations
                if shard_station.lat is None or shard_station.lon is None:
                    old_weight = 0
                else:
                    old_weight = min((shard_station.samples or 0),
                                     self.MAX_OLD_OBSERVATIONS)
                new_lat = ((obs_new_lat * obs_length +
                            (shard_station.lat or 0.0) * old_weight) /
                           (obs_length + old_weight))
                new_lon = ((obs_new_lon * obs_length +
                            (shard_station.lon or 0.0) * old_weight) /
                           (obs_length + old_weight))
                samples = (shard_station.samples or 0) + obs_length
                radius = circle_radius(
                    new_lat, new_lon, max_lat, max_lon, min_lat, min_lon)
                values.update({
                    'lat': new_lat,
                    'lon': new_lon,
                    'max_lat': float(max_lat),
                    'min_lat': float(min_lat),
                    'max_lon': float(max_lon),
                    'min_lon': float(min_lon),
                    'country': country_for_location(new_lat, new_lon),
                    'radius': radius,
                    'samples': samples,
                    'source': None,
                    # use the exact same keys as in the moving case
                    'block_last': shard_station.block_last,
                    'block_count': shard_station.block_count,
                })
                return ('changed', values)

        return (None, None)  # pragma: no cover

    def _shard_observations(self, observations):
        sharded_obs = {}
        for obs in observations:
            if obs is not None:
                shard = WifiShard.shard_model(obs.mac)
                if shard not in sharded_obs:
                    sharded_obs[shard] = defaultdict(list)
                sharded_obs[shard][obs.mac].append(obs)
        return sharded_obs

    def _query_stations(self, shard, shard_values):
        macs = list(shard_values.keys())
        rows = (self.session.query(shard)
                            .filter(shard.mac.in_(macs))).all()

        blocklist = {}
        stations = {}
        for row in rows:
            stations[row.mac] = row
            blocklist[row.mac] = row.blocked(today=self.today)
        return (blocklist, stations)

    def _update_shard(self, shard, shard_values,
                      drop_counter, stats_counter):
        new_data = defaultdict(list)
        blocklist, stations = self._query_stations(shard, shard_values)

        for station_key, observations in shard_values.items():
            if blocklist.get(station_key, False):
                # Drop observations for blocklisted stations.
                drop_counter['blocklisted'] += len(observations)
                continue

            shard_station = stations.get(station_key, None)
            if shard_station is None:
                # We discovered an actual new never before seen station.
                stats_counter['new_station'] += 1

            status, result = self.station_values(
                station_key, shard_station, observations)
            new_data[status].append(result)

            if status in ('moving', 'new_moving'):
                stats_counter['block'] += 1
            else:
                stats_counter['obs'] += len(observations)

        if new_data['new']:
            # do a batch insert of new stations
            stmt = shard.__table__.insert(
                mysql_on_duplicate='samples = samples'  # no-op
            )
            self.session.execute(stmt.values(new_data['new']))

        if new_data['new_moving']:
            # do a batch insert of new moving stations
            stmt = shard.__table__.insert(
                mysql_on_duplicate='block_count = block_count'  # no-op
            )
            self.session.execute(stmt.values(new_data['new_moving']))

        if new_data['moving'] or new_data['changed']:
            # do a batch update of changing and moving stations
            self.session.bulk_update_mappings(
                shard, new_data['changed'] + new_data['moving'])

    def __call__(self, batch=10):
        sharded_obs = self._shard_observations(
            self.data_queue.dequeue(batch=batch))
        if not sharded_obs:
            return

        drop_counter = defaultdict(int)
        stats_counter = defaultdict(int)

        for shard, shard_values in sharded_obs.items():
            self._update_shard(shard, shard_values,
                               drop_counter, stats_counter)

        self.emit_stats(stats_counter, drop_counter)

        if self.data_queue.enough_data(batch=batch):  # pragma: no cover
            self.update_task.apply_async(
                kwargs={'batch': batch},
                countdown=2,
                expires=10)
