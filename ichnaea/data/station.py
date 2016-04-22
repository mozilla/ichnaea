from collections import defaultdict
import time

import numpy
from pymysql.err import InternalError as PyMysqlInternalError
from pymysql.constants.ER import (
    LOCK_WAIT_TIMEOUT,
    LOCK_DEADLOCK,
)
from sqlalchemy.exc import InternalError as SQLInternalError

from ichnaea.geocalc import (
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
    ReportSource,
    StatCounter,
    StatKey,
)
from ichnaea.models.constants import (
    BLUE_MAX_RADIUS,
    CELL_MAX_RADIUS,
    WIFI_MAX_RADIUS,
)
from ichnaea import util


class StationUpdater(object):

    MAX_OLD_WEIGHT = 10000.0
    max_dist_meters = None
    obs_model = None
    station_type = None
    stat_obs_key = None
    stat_station_key = None
    _retriable = (LOCK_DEADLOCK, LOCK_WAIT_TIMEOUT)
    _retries = 3
    _retry_wait = 1.0

    def __init__(self, task, shard_id=None):
        self.task = task
        self.shard_id = shard_id
        self.utcnow = util.utcnow()
        self.today = self.utcnow.date()
        self.data_queues = self.task.app.data_queues
        self.data_queue = self.data_queues[self.queue_prefix + shard_id]

    def base_key_values(self, station_key):
        raise NotImplementedError()

    def base_submit_values(self, station_key, shard_station, observations):
        raise NotImplementedError()

    def query_shard(self, session, shard, keys):
        raise NotImplementedError()

    def add_area_update(self, updated_areas, key):
        pass

    def queue_area_updates(self, pipe, updated_areas):  # pragma: no cover
        pass

    def stat_count(self, type_, action, count):
        if count > 0:
            self.task.stats_client.incr(
                'data.%s.%s' % (type_, action),
                count,
                tags=['type:%s' % self.station_type])

    def emit_stats(self, pipe, stats_counter):
        StatCounter(self.stat_obs_key, self.today).incr(
            pipe, stats_counter['obs'])
        StatCounter(self.stat_station_key, self.today).incr(
            pipe, stats_counter['new'])

        self.stat_count('observation', 'insert', stats_counter['obs'])
        self.stat_count('station', 'blocklist', stats_counter['block'])
        self.stat_count('station', 'confirm', stats_counter['confirm'])
        self.stat_count('station', 'new', stats_counter['new'])

    def confirm_values(self, station_key):
        values = self.base_key_values(station_key)
        values['last_seen'] = self.today
        return ('confirm', values)

    def change_values(self, station_key, shard_station,
                      observations, data, source):
        # move and change values need to have the exact same dict keys,
        # as they get combined into one bulk_update_mappings calls.
        values = self.base_submit_values(
            station_key, shard_station, observations)
        values.update({
            'last_seen': self.today, 'modified': self.utcnow,
            'lat': data['lat'], 'lon': data['lon'],
            'max_lat': data['max_lat'], 'min_lat': data['min_lat'],
            'max_lon': data['max_lon'], 'min_lon': data['min_lon'],
            'radius': data['radius'], 'region': data['region'],
            'samples': data['samples'], 'source': source,
            'weight': data['weight'],
            'block_first': shard_station.block_first,
            'block_last': shard_station.block_last,
            'block_count': shard_station.block_count,
        })
        return ('change', values)

    def move_values(self, station_key, observations, shard_station):
        # move and change values need to have the exact same dict keys,
        # as they get combined into one bulk_update_mappings calls.
        values = self.base_submit_values(
            station_key, shard_station, observations)
        values.update({
            'last_seen': None, 'modified': self.utcnow,
            'lat': None, 'lon': None,
            'max_lat': None, 'min_lat': None,
            'max_lon': None, 'min_lon': None,
            'radius': None, 'region': shard_station.region,
            'samples': None, 'source': None,
            'weight': None,
            'block_first': shard_station.block_first or self.today,
            'block_last': self.today,
            'block_count': (shard_station.block_count or 0) + 1,
        })
        return ('move', values)

    def new_values(self, station_key, observations, data, source):
        values = self.base_submit_values(station_key, None, observations)
        values.update({
            'created': self.utcnow, 'last_seen': self.today,
            'modified': self.utcnow,
            'lat': data['lat'], 'lon': data['lon'],
            'max_lat': data['max_lat'], 'min_lat': data['min_lat'],
            'max_lon': data['max_lon'], 'min_lon': data['min_lon'],
            'radius': data['radius'], 'region': data['region'],
            'samples': data['samples'], 'source': source,
            'weight': data['weight'],
        })
        return ('new', values)

    def new_move_values(self, station_key, observations):
        values = self.base_submit_values(station_key, None, observations)
        values.update({
            'created': self.utcnow, 'last_seen': None,
            'modified': self.utcnow,
            'block_first': self.today,
            'block_last': self.today,
            'block_count': 1,
        })
        return ('new_move', values)

    def bounded_samples_weight(self, samples, weight):
        # put in maximum value to avoid overflow of DB column
        return (min(samples, 4294967295), min(weight, 1000000000.0))

    def aggregate_obs(self, observations):
        positions = numpy.array(
            [(obs.lat, obs.lon) for obs in observations],
            dtype=numpy.double)

        max_lat, max_lon = positions.max(axis=0)
        min_lat, min_lon = positions.min(axis=0)

        box_distance = distance(min_lat, min_lon, max_lat, max_lon)
        if box_distance > self.max_dist_meters:
            return None

        weights = numpy.array(
            [obs.weight for obs in observations],
            dtype=numpy.double)

        lat, lon = numpy.average(positions, axis=0, weights=weights)
        lat = float(lat)
        lon = float(lon)
        radius = circle_radius(lat, lon, max_lat, max_lon, min_lat, min_lon)
        region = GEOCODER.region(lat, lon)

        samples, weight = self.bounded_samples_weight(
            len(observations), float(weights.sum()))

        return {
            'positions': positions, 'weights': weights,
            'lat': lat, 'lon': lon,
            'max_lat': float(max_lat), 'min_lat': float(min_lat),
            'max_lon': float(max_lon), 'min_lon': float(min_lon),
            'radius': radius, 'region': region,
            'samples': samples, 'weight': weight,
        }

    def aggregate_station_obs(self, shard_station, obs_data):
        def get_nan(name):
            value = getattr(shard_station, name, None)
            return numpy.nan if value is None else value

        positions = numpy.append(obs_data['positions'], [
            (get_nan('lat'), get_nan('lon')),
            (get_nan('max_lat'), get_nan('max_lon')),
            (get_nan('min_lat'), get_nan('min_lon')),
        ], axis=0)

        max_lat, max_lon = numpy.nanmax(positions, axis=0)
        min_lat, min_lon = numpy.nanmin(positions, axis=0)

        box_distance = distance(min_lat, min_lon, max_lat, max_lon)
        if box_distance > self.max_dist_meters:
            return None

        if shard_station.lat is None or shard_station.lon is None:
            old_weight = 0.0
        else:
            old_weight = min((shard_station.weight or 0.0),
                             self.MAX_OLD_WEIGHT)

        lat = ((obs_data['lat'] * obs_data['weight'] +
                (shard_station.lat or 0.0) * old_weight) /
               (obs_data['weight'] + old_weight))
        lon = ((obs_data['lon'] * obs_data['weight'] +
                (shard_station.lon or 0.0) * old_weight) /
               (obs_data['weight'] + old_weight))

        radius = circle_radius(lat, lon, max_lat, max_lon, min_lat, min_lon)
        region = shard_station.region
        if (region and not GEOCODER.in_region(lat, lon, region)):
            # reset region if it no longer matches
            region = None
        if not region:
            region = GEOCODER.region(lat, lon)

        samples, weight = self.bounded_samples_weight(
            (shard_station.samples or 0) + obs_data['samples'],
            (shard_station.weight or 0.0) + obs_data['weight'])

        return {
            'lat': lat, 'lon': lon,
            'max_lat': float(max_lat), 'min_lat': float(min_lat),
            'max_lon': float(max_lon), 'min_lon': float(min_lon),
            'radius': radius, 'region': region,
            'samples': samples, 'weight': weight,
        }

    def query_values(self, station_key, shard_station, observations):
        if shard_station and shard_station.last_seen == self.today:
            # 0. shard station was confirmed today
            return (None, None)

        if (shard_station and (shard_station.lat is not None and
                               shard_station.lon is not None)):
            # 1. shard station
            agree = 0
            disagree = 0
            for obs in observations:
                obs_distance = distance(obs.lat, obs.lon,
                                        shard_station.lat, shard_station.lon)
                if obs_distance <= self.max_dist_meters:
                    agree += 1
                else:
                    disagree += 1

            if agree >= disagree:
                # 1.a. majority of obs agree with station
                return self.confirm_values(station_key)

            if not agree and disagree:
                # 1.b. no obs agrees with station
                return self.move_values(
                    station_key, observations, shard_station)

        if not shard_station:
            # 2. no prior station
            obs_data = self.aggregate_obs(observations)
            if obs_data is None:
                # 2.a. obs disagree
                return self.new_move_values(station_key, observations)
            else:
                # 2.b. obs agree -> TODO new
                return (None, None)

        return (None, None)  # pragma: no cover

    def submit_values(self, station_key, shard_station, observations):
        obs_data = self.aggregate_obs(observations)

        if obs_data is None:
            # 0. the new observations are already too far apart
            if not shard_station:
                # 0.a. no shard station
                return self.new_move_values(station_key, observations)
            else:
                # 0.b. shard station
                return self.move_values(
                    station_key, observations, shard_station)

        if shard_station is None:
            # 1. no shard station
            # 1.a. obs agree
            # 1.b. obs disagree (already covered in 0.a.)
            return self.new_values(
                station_key, observations, obs_data, ReportSource.gnss)
        else:
            # 2. shard station
            data = self.aggregate_station_obs(shard_station, obs_data)
            if data is None:
                # 2.a. obs disagree with station
                return self.move_values(
                    station_key, observations, shard_station)
            else:
                # 2.b. obs agree with station
                return self.change_values(
                    station_key, shard_station, observations,
                    data, ReportSource.gnss)

        return (None, None)  # pragma: no cover

    def query_stations(self, session, shard, shard_values):
        blocklist = {}
        stations = {}

        keys = list(shard_values.keys())
        rows = self.query_shard(session, shard, keys)
        for row in rows:
            unique_key = row.unique_key
            stations[unique_key] = row
            blocklist[unique_key] = row.blocked(today=self.today)

        return (blocklist, stations)

    def update_shard(self, session, shard, shard_values, stats_counter):
        updated_areas = set()
        new_data = defaultdict(list)
        blocklist, stations = self.query_stations(
            session, shard, shard_values)

        for station_key, observations in shard_values.items():
            # Count all observations.
            stats_counter['obs'] += len(observations)

            if blocklist.get(station_key, False):
                # Drop observations for blocklisted stations.
                continue

            query_observations = []
            submit_observations = []

            for obs in observations:
                if obs.source is ReportSource.query:
                    query_observations.append(obs)
                else:
                    submit_observations.append(obs)

            shard_station = stations.get(station_key, None)
            if not submit_observations:
                # Only query observations.
                status, result = self.query_values(
                    station_key, shard_station, query_observations)
            else:
                # At least one submit observation, ignore query_observations.
                status, result = self.submit_values(
                    station_key, shard_station, submit_observations)

            if not status:
                continue

            new_data[status].append(result)

            if status in ('change', 'confirm'):
                stats_counter['confirm'] += 1
            if status in ('new', 'new_move'):
                stats_counter['new'] += 1
            if status in ('move', 'new_move'):
                stats_counter['block'] += 1

            # track potential updates to dependent areas
            self.add_area_update(updated_areas, station_key)

        if new_data['new']:
            session.execute(shard.__table__.insert(
                mysql_on_duplicate='samples = samples').values(
                new_data['new']))

        if new_data['new_move']:
            session.execute(shard.__table__.insert(
                mysql_on_duplicate='block_count = block_count').values(
                new_data['new_move']))

        if new_data['change'] or new_data['move']:
            session.bulk_update_mappings(
                shard, new_data['change'] + new_data['move'])

        if new_data['confirm']:
            session.bulk_update_mappings(shard, new_data['confirm'])

        return updated_areas

    def shard_observations(self, observations):
        sharded_obs = {}
        for obs in observations:
            obs = self.obs_model.from_json(obs)
            if obs is not None:
                if not obs.weight:
                    # Filter out observations with too little weight.
                    continue
                shard = obs.shard_model
                if shard not in sharded_obs:
                    sharded_obs[shard] = defaultdict(list)
                sharded_obs[shard][obs.unique_key].append(obs)
        return sharded_obs

    def __call__(self):
        sharded_obs = self.shard_observations(self.data_queue.dequeue())
        if not sharded_obs:
            return

        success = False
        for i in range(self._retries):
            try:
                stats_counter = defaultdict(int)
                updated_areas = set()

                with self.task.db_session() as session:
                    for shard, shard_values in sharded_obs.items():
                        updated_areas.update(self.update_shard(
                            session, shard, shard_values, stats_counter))

                success = True
            except SQLInternalError as exc:
                if (isinstance(exc.orig, PyMysqlInternalError) and
                        exc.orig.args[0] in self._retriable):
                    success = False
                    time.sleep(self._retry_wait * (i ** 2 + 1))
                else:  # pragma: no cover
                    raise

            if success:
                break

        if success:
            with self.task.redis_pipeline() as pipe:
                if updated_areas:
                    self.queue_area_updates(pipe, updated_areas)

                self.emit_stats(pipe, stats_counter)

            if self.data_queue.ready():  # pragma: no cover
                self.task.apply_countdown(kwargs={'shard_id': self.shard_id})


class MacUpdater(StationUpdater):

    def base_key_values(self, station_key):
        return {'mac': station_key}

    def base_submit_values(self, station_key, shard_station, observations):
        return self.base_key_values(station_key)

    def query_shard(self, session, shard, keys):
        return (session.query(shard)
                       .filter(shard.mac.in_(keys))).all()


class BlueUpdater(MacUpdater):

    max_dist_meters = BLUE_MAX_RADIUS
    obs_model = BlueObservation
    queue_prefix = 'update_blue_'
    station_type = 'blue'
    stat_obs_key = StatKey.blue
    stat_station_key = StatKey.unique_blue


class WifiUpdater(MacUpdater):

    max_dist_meters = WIFI_MAX_RADIUS
    obs_model = WifiObservation
    queue_prefix = 'update_wifi_'
    station_type = 'wifi'
    stat_obs_key = StatKey.wifi
    stat_station_key = StatKey.unique_wifi


class CellUpdater(StationUpdater):

    max_dist_meters = CELL_MAX_RADIUS
    obs_model = CellObservation
    queue_prefix = 'update_cell_'
    station_type = 'cell'
    stat_obs_key = StatKey.cell
    stat_station_key = StatKey.unique_cell

    def base_key_values(self, station_key):
        radio, mcc, mnc, lac, cid = decode_cellid(station_key)
        return {
            'cellid': station_key,
            'radio': radio,
            'mcc': mcc,
            'mnc': mnc,
            'lac': lac,
            'cid': cid,
        }

    def base_submit_values(self, station_key, shard_station, observations):
        values = self.base_key_values(station_key)

        psc = None
        if shard_station:
            psc = shard_station.psc

        if observations:
            pscs = [obs.psc for obs in observations if obs.psc is not None]
            if pscs:
                psc = pscs[-1]
        values['psc'] = psc
        return values

    def query_shard(self, session, shard, keys):
        return (session.query(shard)
                       .filter(shard.cellid.in_(keys))).all()

    def add_area_update(self, updated_areas, key):
        updated_areas.add(encode_cellarea(*decode_cellid(key)[:4]))

    def queue_area_updates(self, pipe, updated_areas):
        data_queue = self.data_queues['update_cellarea']
        data_queue.enqueue(list(updated_areas), pipe=pipe)
