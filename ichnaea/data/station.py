from collections import defaultdict
from datetime import timedelta
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
    station_blocked,
    StatCounter,
    StatKey,
)
from ichnaea.models.constants import (
    BLUE_MAX_RADIUS,
    CELL_MAX_RADIUS,
    WIFI_MAX_RADIUS,
)
from ichnaea import util


class StationState(object):

    MAX_DIST_METERS = None
    MAX_OLD_WEIGHT = 10000.0
    MAX_OLD_DAYS = 365

    def __init__(self, station_key, station,
                 source, observations, now, today):
        self.station_key = station_key
        self.station = station
        self.source = source
        self.observations = observations
        self.now = now
        self.today = today
        self.one_year = today - timedelta(days=self.MAX_OLD_DAYS)
        self.obs_data = self.aggregate_obs()

    def base_key(self):
        raise NotImplementedError()

    def submit_key(self):
        raise NotImplementedError()

    def has_position(self):
        return bool(
            self.station and
            self.station.lat is not None and
            self.station.lon is not None)

    def is_old_position(self):
        return bool(self.station and self.station.modified and
                    self.station.modified.date() < self.one_year)

    def transition(self):
        station_state = 'none'
        if self.station:
            if self.has_position():
                if self.confirm_station_obs():
                    if (self.station.source is ReportSource.query):
                        station_source = 'query'
                    else:
                        station_source = 'gnss'
                    station_state = 'agree_%s_position' % station_source
                else:
                    if self.is_old_position():
                        station_state = 'disagree_old_position'
                    else:
                        station_state = 'disagree_position'
            else:
                station_state = 'no_position'

        obs_state = None
        consistent_obs = bool(self.obs_data is not None)
        if self.source is ReportSource.gnss:
            if consistent_obs:
                obs_state = 'gnss_consistent'
            else:
                obs_state = 'gnss_inconsistent'
        elif self.source is ReportSource.query:
            if consistent_obs:
                obs_state = 'query_consistent'
            else:
                obs_state = 'query_inconsistent'

        transitions = {
            # (station_state, obs_state)
            ('none', 'gnss_consistent'): self.new,
            ('none', 'query_consistent'): self.new,
            ('none', 'gnss_inconsistent'): self.new_block,
            ('none', 'query_inconsistent'): self.new_block,
            ('no_position', 'gnss_consistent'): self.change,
            ('no_position', 'query_consistent'): self.change,
            ('no_position', 'gnss_inconsistent'): None,
            ('no_position', 'query_inconsistent'): None,
            ('agree_gnss_position', 'gnss_consistent'): self.change,
            ('agree_gnss_position', 'query_consistent'): self.confirm,
            ('agree_gnss_position', 'gnss_inconsistent'): self.block,
            ('agree_gnss_position', 'query_inconsistent'): self.block,
            ('agree_query_position', 'gnss_consistent'): self.replace,
            ('agree_query_position', 'query_consistent'): self.change,
            ('agree_query_position', 'gnss_inconsistent'): self.block,
            ('agree_query_position', 'query_inconsistent'): self.block,
            ('disagree_position', 'gnss_consistent'): self.block,
            ('disagree_position', 'query_consistent'): self.block,
            ('disagree_position', 'gnss_inconsistent'): self.block,
            ('disagree_position', 'query_inconsistent'): self.block,
            ('disagree_old_position', 'gnss_consistent'): self.replace,
            ('disagree_old_position', 'query_consistent'): self.replace,
            ('disagree_old_position', 'gnss_inconsistent'): self.block,
            ('disagree_old_position', 'query_inconsistent'): self.block,
        }
        return transitions.get((station_state, obs_state))

    def confirm_station_obs(self):
        confirm = False
        if self.has_position():
            # station with position
            confirm = True
            for obs in self.observations:
                obs_distance = distance(obs.lat, obs.lon,
                                        self.station.lat, self.station.lon)
                if obs_distance > self.MAX_DIST_METERS:
                    confirm = False
                    break

        return confirm

    def confirm(self):
        if self.station and self.station.last_seen == self.today:
            # already confirmed today
            return (None, None)

        values = self.base_key()
        values['last_seen'] = self.today
        return ('confirm', values)

    def block(self):
        # block and _change values need to have the exact same dict keys,
        # as they get combined into one bulk_update_mappings calls.
        values = self.submit_key()
        values.update({
            'last_seen': None, 'modified': self.now,
            'lat': None, 'lon': None,
            'max_lat': None, 'min_lat': None,
            'max_lon': None, 'min_lon': None,
            'radius': None, 'region': self.station.region,
            'samples': None, 'source': None,
            'weight': None,
            'block_first': self.station.block_first or self.today,
            'block_last': self.today,
            'block_count': (self.station.block_count or 0) + 1,
        })
        return ('block', values)

    def _change(self, update=True):
        # block and _change values need to have the exact same dict keys,
        # as they get combined into one bulk_update_mappings calls.
        if update:
            data = self.aggregate_station_obs()
        else:
            data = self.obs_data
        values = self.submit_key()
        values.update({
            'last_seen': self.today, 'modified': self.now,
            'lat': data['lat'], 'lon': data['lon'],
            'max_lat': data['max_lat'], 'min_lat': data['min_lat'],
            'max_lon': data['max_lon'], 'min_lon': data['min_lon'],
            'radius': data['radius'], 'region': data['region'],
            'samples': data['samples'], 'source': self.source,
            'weight': data['weight'],
            'block_first': self.station.block_first,
            'block_last': self.station.block_last,
            'block_count': self.station.block_count,
        })
        return values

    def change(self):
        return ('change', self._change(update=True))

    def replace(self):
        return ('replace', self._change(update=False))

    def new(self):
        data = self.obs_data
        values = self.submit_key()
        values.update({
            'created': self.now, 'last_seen': self.today,
            'modified': self.now,
            'lat': data['lat'], 'lon': data['lon'],
            'max_lat': data['max_lat'], 'min_lat': data['min_lat'],
            'max_lon': data['max_lon'], 'min_lon': data['min_lon'],
            'radius': data['radius'], 'region': data['region'],
            'samples': data['samples'], 'source': self.source,
            'weight': data['weight'],
        })
        return ('new', values)

    def new_block(self):
        values = self.submit_key()
        values.update({
            'created': self.now, 'last_seen': None,
            'modified': self.now,
            'block_first': self.today,
            'block_last': self.today,
            'block_count': 1,
        })
        return ('new_block', values)

    def bounded_samples_weight(self, samples, weight):
        # put in maximum value to avoid overflow of DB column
        return (min(samples, 4294967295), min(weight, 1000000000.0))

    def aggregate_obs(self):
        positions = numpy.array(
            [(obs.lat, obs.lon) for obs in self.observations],
            dtype=numpy.double)

        max_lat, max_lon = positions.max(axis=0)
        min_lat, min_lon = positions.min(axis=0)

        box_distance = distance(min_lat, min_lon, max_lat, max_lon)
        if box_distance > self.MAX_DIST_METERS:
            return None

        weights = numpy.array(
            [obs.weight for obs in self.observations],
            dtype=numpy.double)

        lat, lon = numpy.average(positions, axis=0, weights=weights)
        lat = float(lat)
        lon = float(lon)
        radius = circle_radius(lat, lon, max_lat, max_lon, min_lat, min_lon)
        region = GEOCODER.region(lat, lon)

        samples, weight = self.bounded_samples_weight(
            len(self.observations), float(weights.sum()))

        return {
            'positions': positions, 'weights': weights,
            'lat': lat, 'lon': lon,
            'max_lat': float(max_lat), 'min_lat': float(min_lat),
            'max_lon': float(max_lon), 'min_lon': float(min_lon),
            'radius': radius, 'region': region,
            'samples': samples, 'weight': weight,
        }

    def aggregate_station_obs(self):
        station = self.station
        obs_data = self.obs_data

        def get_nan(name):
            value = getattr(station, name, None)
            return numpy.nan if value is None else value

        positions = numpy.append(obs_data['positions'], [
            (get_nan('lat'), get_nan('lon')),
            (get_nan('max_lat'), get_nan('max_lon')),
            (get_nan('min_lat'), get_nan('min_lon')),
        ], axis=0)

        max_lat, max_lon = numpy.nanmax(positions, axis=0)
        min_lat, min_lon = numpy.nanmin(positions, axis=0)

        if station.lat is None or station.lon is None:
            old_weight = 0.0
        else:
            old_weight = min((station.weight or 0.0), self.MAX_OLD_WEIGHT)

        lat = ((obs_data['lat'] * obs_data['weight'] +
                (station.lat or 0.0) * old_weight) /
               (obs_data['weight'] + old_weight))
        lon = ((obs_data['lon'] * obs_data['weight'] +
                (station.lon or 0.0) * old_weight) /
               (obs_data['weight'] + old_weight))

        radius = circle_radius(lat, lon, max_lat, max_lon, min_lat, min_lon)
        region = station.region
        if (region and not GEOCODER.in_region(lat, lon, region)):
            # reset region if it no longer matches
            region = None
        if not region:
            region = GEOCODER.region(lat, lon)

        samples, weight = self.bounded_samples_weight(
            (station.samples or 0) + obs_data['samples'],
            (station.weight or 0.0) + obs_data['weight'])

        return {
            'lat': lat, 'lon': lon,
            'max_lat': float(max_lat), 'min_lat': float(min_lat),
            'max_lon': float(max_lon), 'min_lon': float(min_lon),
            'radius': radius, 'region': region,
            'samples': samples, 'weight': weight,
        }


class MacState(StationState):

    def base_key(self):
        return {'mac': self.station_key}

    def submit_key(self):
        return self.base_key()


class BlueState(MacState):

    MAX_DIST_METERS = BLUE_MAX_RADIUS


class WifiState(MacState):

    MAX_DIST_METERS = WIFI_MAX_RADIUS


class CellState(StationState):

    MAX_DIST_METERS = CELL_MAX_RADIUS

    def base_key(self):
        radio, mcc, mnc, lac, cid = decode_cellid(self.station_key)
        return {
            'cellid': self.station_key,
            'radio': radio,
            'mcc': mcc,
            'mnc': mnc,
            'lac': lac,
            'cid': cid,
        }

    def submit_key(self):
        values = self.base_key()

        psc = None
        if self.station:
            psc = self.station.psc

        if self.observations:
            pscs = [obs.psc for obs in self.observations
                    if obs.psc is not None]
            if pscs:
                psc = pscs[-1]
        values['psc'] = psc
        return values


class StationUpdater(object):

    obs_model = None
    station_state = None
    station_type = None
    stat_obs_key = None
    stat_station_key = None
    _retriable = (LOCK_DEADLOCK, LOCK_WAIT_TIMEOUT)
    _retries = 3
    _retry_wait = 1.0

    def __init__(self, task, shard_id=None):
        self.task = task
        self.shard_id = shard_id
        self.now = util.utcnow()
        self.today = self.now.date()
        self.data_queues = self.task.app.data_queues
        self.data_queue = self.data_queues[self.queue_prefix + shard_id]

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

    def query_stations(self, session, shard, shard_values):
        blocklist = {}
        stations = {}

        keys = list(shard_values.keys())
        rows = self.query_shard(session, shard, keys)
        for row in rows:
            unique_key = row.unique_key
            stations[unique_key] = row
            blocklist[unique_key] = station_blocked(row, self.today)

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

            grouped_obs = {ReportSource.gnss: [], ReportSource.query: []}
            for obs in observations:
                if obs.source is ReportSource.query:
                    grouped_obs[obs.source].append(obs)
                else:
                    # treat fused, fixed as gnss
                    grouped_obs[ReportSource.gnss].append(obs)

            station = stations.get(station_key, None)
            source = ReportSource.gnss
            if not grouped_obs[source]:
                # Only query observations.
                source = ReportSource.query

            state = self.station_state(
                station_key, station, source, grouped_obs[source],
                self.now, self.today)

            transition = state.transition()
            if transition is not None:
                status, result = transition()
            else:
                status, result = (None, None)

            if not status:
                continue

            new_data[status].append(result)

            if status in ('change', 'confirm', 'replace'):
                stats_counter['confirm'] += 1
            if status in ('new', 'new_block'):
                stats_counter['new'] += 1
            if status in ('block', 'new_block'):
                stats_counter['block'] += 1

            # track potential updates to dependent areas
            if status != 'confirm':
                self.add_area_update(updated_areas, station_key)

        if new_data['new']:
            session.execute(shard.__table__.insert(
                mysql_on_duplicate='samples = samples').values(
                new_data['new']))

        if new_data['new_block']:
            session.execute(shard.__table__.insert(
                mysql_on_duplicate='block_count = block_count').values(
                new_data['new_block']))

        updates = new_data['block'] + new_data['change'] + new_data['replace']
        if updates:
            session.bulk_update_mappings(shard, updates)

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

    def query_shard(self, session, shard, keys):
        return (session.query(shard)
                       .filter(shard.mac.in_(keys))).all()


class BlueUpdater(MacUpdater):

    obs_model = BlueObservation
    queue_prefix = 'update_blue_'
    station_state = BlueState
    station_type = 'blue'
    stat_obs_key = StatKey.blue
    stat_station_key = StatKey.unique_blue


class WifiUpdater(MacUpdater):

    obs_model = WifiObservation
    queue_prefix = 'update_wifi_'
    station_state = WifiState
    station_type = 'wifi'
    stat_obs_key = StatKey.wifi
    stat_station_key = StatKey.unique_wifi


class CellUpdater(StationUpdater):

    obs_model = CellObservation
    queue_prefix = 'update_cell_'
    station_state = CellState
    station_type = 'cell'
    stat_obs_key = StatKey.cell
    stat_station_key = StatKey.unique_cell

    def query_shard(self, session, shard, keys):
        return (session.query(shard)
                       .filter(shard.cellid.in_(keys))).all()

    def add_area_update(self, updated_areas, key):
        updated_areas.add(encode_cellarea(*decode_cellid(key)[:4]))

    def queue_area_updates(self, pipe, updated_areas):
        data_queue = self.data_queues['update_cellarea']
        data_queue.enqueue(list(updated_areas), pipe=pipe)
