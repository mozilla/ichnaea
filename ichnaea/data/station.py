from collections import defaultdict

import numpy

from ichnaea.data.base import DataTask
from ichnaea.geocalc import (
    centroid_weighted,
    circle_radius,
    distance,
)
from ichnaea.geocode import GEOCODER
from ichnaea.models import (
    decode_cellid,
    encode_cellarea,
    BlueObservation,
    CellObservation,
    WifiObservation,
    StatCounter,
    StatKey,
)
from ichnaea.models.constants import (
    BLUE_MAX_RADIUS,
    CELL_MAX_RADIUS,
    WIFI_MAX_RADIUS,
)
from ichnaea import util


class StationUpdater(DataTask):

    MAX_OLD_WEIGHT = 10000.0
    max_dist_meters = None
    obs_model = None
    station_type = None
    stat_obs_key = None
    stat_station_key = None

    def __init__(self, task, session, pipe, shard_id=None):
        super(StationUpdater, self).__init__(task, session)
        self.pipe = pipe
        self.shard_id = shard_id
        self.updated_areas = set()
        self.utcnow = util.utcnow()
        self.today = self.utcnow.date()
        self.data_queues = self.task.app.data_queues
        self.data_queue = self.data_queues[self.queue_prefix + shard_id]

    def stat_count(self, action, count, reason=None):
        if count > 0:
            tags = ['type:%s' % self.station_type]
            if reason:
                tags.append('reason:%s' % reason)
            self.stats_client.incr(
                'data.observation.%s' % action,
                count,
                tags=tags)

    def add_area_update(self, key):
        pass

    def queue_area_updates(self):  # pragma: no cover
        pass

    def emit_stats(self, stats_counter, drop_counter):
        day = self.today
        StatCounter(self.stat_obs_key, day).incr(
            self.pipe, stats_counter['obs'])
        StatCounter(self.stat_station_key, day).incr(
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

    def _base_station_values(self, station_key, observations):
        raise NotImplementedError()

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
        values = self._base_station_values(station_key, observations)

        obs_positions = numpy.array(
            [(obs.lat, obs.lon) for obs in observations],
            dtype=numpy.double)
        obs_length = len(observations)

        obs_weights = numpy.array(
            [obs.weight for obs in observations],
            dtype=numpy.double)
        obs_weight = float(obs_weights.sum())

        obs_new_lat, obs_new_lon = centroid_weighted(
            obs_positions, obs_weights)

        obs_max_lat, obs_max_lon = obs_positions.max(axis=0)
        obs_min_lat, obs_min_lon = obs_positions.min(axis=0)
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
                    'radius': None,
                    'region': shard_station.region,
                    'samples': None,
                    'source': None,
                    'weight': None,
                    'block_first': shard_station.block_first or self.today,
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
                'radius': radius,
                'region': GEOCODER.region(obs_new_lat, obs_new_lon),
                'samples': obs_length,
                'source': None,
                'weight': obs_weight,
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
                    'radius': None,
                    'region': shard_station.region,
                    'samples': None,
                    'source': None,
                    'weight': None,
                    'block_first': shard_station.block_first or self.today,
                    'block_last': self.today,
                    'block_count': block_count + 1,
                })
                return ('moving', values)
            else:
                # shard_station + agreeing observations
                if shard_station.lat is None or shard_station.lon is None:
                    old_weight = 0
                else:
                    old_weight = min((shard_station.weight or 0.0),
                                     self.MAX_OLD_WEIGHT)

                new_lat = ((obs_new_lat * obs_weight +
                            (shard_station.lat or 0.0) * old_weight) /
                           (obs_weight + old_weight))
                new_lon = ((obs_new_lon * obs_weight +
                            (shard_station.lon or 0.0) * old_weight) /
                           (obs_weight + old_weight))

                # put in maximum value to avoid overflow of DB column
                samples = min((shard_station.samples or 0) + obs_length,
                              4294967295)
                weight = min((shard_station.weight or 0.0) + obs_weight,
                             1000000000.0)

                radius = circle_radius(
                    new_lat, new_lon, max_lat, max_lon, min_lat, min_lon)
                region = shard_station.region
                if (region and not GEOCODER.in_region(
                        new_lat, new_lon, region)):
                    # reset region if it no longer matches
                    region = None
                if not region:
                    region = GEOCODER.region(new_lat, new_lon)
                values.update({
                    'lat': new_lat,
                    'lon': new_lon,
                    'max_lat': float(max_lat),
                    'min_lat': float(min_lat),
                    'max_lon': float(max_lon),
                    'min_lon': float(min_lon),
                    'radius': radius,
                    'region': region,
                    'samples': samples,
                    'source': None,
                    'weight': weight,
                    # use the exact same keys as in the moving case
                    'block_first': shard_station.block_first,
                    'block_last': shard_station.block_last,
                    'block_count': shard_station.block_count,
                })
                return ('changed', values)

        return (None, None)  # pragma: no cover

    def _shard_observations(self, observations):
        sharded_obs = {}
        for obs in observations:
            if isinstance(obs, dict):
                # BBB check can be removed
                obs = self.obs_model.from_json(obs)
            if obs is not None:
                shard = obs.shard_model
                if shard not in sharded_obs:
                    sharded_obs[shard] = defaultdict(list)
                sharded_obs[shard][obs.unique_key].append(obs)
        return sharded_obs

    def _query_shard(self, shard, keys):
        raise NotImplementedError()

    def _query_stations(self, shard, shard_values):
        blocklist = {}
        stations = {}

        keys = list(shard_values.keys())
        rows = self._query_shard(shard, keys)
        for row in rows:
            unique_key = row.unique_key
            stations[unique_key] = row
            blocklist[unique_key] = row.blocked(today=self.today)

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

            # track potential updates to dependent areas
            self.add_area_update(station_key)

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

        if self.updated_areas:
            self.queue_area_updates()

        self.emit_stats(stats_counter, drop_counter)

        if self.data_queue.enough_data(batch=batch):  # pragma: no cover
            self.task.apply_async(
                kwargs={'batch': batch, 'shard_id': self.shard_id},
                countdown=5,
                expires=10)


class BlueUpdater(StationUpdater):

    max_dist_meters = BLUE_MAX_RADIUS
    obs_model = BlueObservation
    queue_prefix = 'update_blue_'
    station_type = 'blue'
    stat_obs_key = StatKey.blue
    stat_station_key = StatKey.unique_blue

    def _base_station_values(self, station_key, observations):
        return {
            'mac': station_key,
            'modified': self.utcnow,
        }

    def _query_shard(self, shard, keys):
        return (self.session.query(shard)
                            .filter(shard.mac.in_(keys))).all()


class CellUpdater(StationUpdater):

    max_dist_meters = CELL_MAX_RADIUS
    obs_model = CellObservation
    queue_prefix = 'update_cell_'
    station_type = 'cell'
    stat_obs_key = StatKey.cell
    stat_station_key = StatKey.unique_cell

    def add_area_update(self, key):
        self.updated_areas.add(encode_cellarea(*decode_cellid(key)[:4]))

    def queue_area_updates(self):
        data_queue = self.data_queues['update_cellarea']
        data_queue.enqueue(list(self.updated_areas),
                           pipe=self.pipe, json=False)

    def _base_station_values(self, station_key, observations):
        radio, mcc, mnc, lac, cid = decode_cellid(station_key)
        if observations:
            psc = observations[-1].psc
        return {
            'cellid': station_key,
            'radio': radio,
            'mcc': mcc,
            'mnc': mnc,
            'lac': lac,
            'cid': cid,
            'psc': psc,
            'modified': self.utcnow,
        }

    def _query_shard(self, shard, keys):
        return (self.session.query(shard)
                            .filter(shard.cellid.in_(keys))).all()


class WifiUpdater(StationUpdater):

    max_dist_meters = WIFI_MAX_RADIUS
    obs_model = WifiObservation
    queue_prefix = 'update_wifi_'
    station_type = 'wifi'
    stat_obs_key = StatKey.wifi
    stat_station_key = StatKey.unique_wifi

    def _base_station_values(self, station_key, observations):
        return {
            'mac': station_key,
            'modified': self.utcnow,
        }

    def _query_shard(self, shard, keys):
        return (self.session.query(shard)
                            .filter(shard.mac.in_(keys))).all()
