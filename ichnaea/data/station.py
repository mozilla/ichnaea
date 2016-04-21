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

    def _base_key_values(self, station_key):
        raise NotImplementedError()

    def _base_submit_values(self, station_key, shard_station, observations):
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
            pipe, stats_counter['new_station'])

        self.stat_count('observation', 'insert', stats_counter['obs'])
        self.stat_count('station', 'blocklist', stats_counter['block'])
        self.stat_count('station', 'confirm', stats_counter['confirm'])
        self.stat_count('station', 'new', stats_counter['new_station'])

    def station_values(self, station_key, shard_station, observations):
        """
        Return two-tuple of status, value dict where status is one of:
        `new`, `new_move`, `move`, `change`, `confirm`.
        """
        # cases:
        # A. we only get query observations
        # A.0. observations disagree -> ignore
        # A.1. no shard station
        # A.1.a. obs agree -> TODO ignore
        # A.2. shard station
        # A.2.a. obs disagree -> return move
        # A.2.b. obs agree -> return confirm
        # B. we get submit observations
        # B.0. observations disagree
        # B.0.a. no shard station, return new_move
        # B.0.b. shard station, return move
        # B.1. no shard station
        # B.1.a. obs agree -> return new
        # B.2. shard station
        # B.2.a. obs disagree -> return move
        # B.2.b. obs agree -> return change
        query_observations = []
        submit_observations = []

        for obs in observations:
            if obs.source is ReportSource.query:
                query_observations.append(obs)
            else:
                submit_observations.append(obs)

        if not submit_observations:
            if (not shard_station or
                    (shard_station.lat is None or shard_station is None)):
                # no prior station or a station without a position
                return (None, None)

            if shard_station.last_seen == self.today:
                # station was already confirmed today
                return (None, None)

            agree = 0
            disagree = 0
            for obs in query_observations:
                obs_distance = distance(obs.lat, obs.lon,
                                        shard_station.lat, shard_station.lon)
                if obs_distance <= self.max_dist_meters:
                    agree += 1
                else:
                    disagree += 1

            if agree >= disagree:
                # we got more agreeing than disagreeing observations
                values = self._base_key_values(station_key)
                values['last_seen'] = self.today
                return ('confirm', values)

            if not agree and disagree:
                # we got only disagreeing observations
                block_count = shard_station.block_count or 0
                values = self._base_submit_values(
                    station_key, shard_station, query_observations)
                values.update({
                    'last_seen': None,
                    'modified': self.utcnow,
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
                return ('move', values)

            return (None, None)  # pragma: no cover

        created = self.utcnow
        values = self._base_submit_values(
            station_key, shard_station, submit_observations)

        obs_positions = numpy.array(
            [(obs.lat, obs.lon) for obs in submit_observations],
            dtype=numpy.double)
        obs_length = len(submit_observations)

        obs_weights = numpy.array(
            [obs.weight for obs in submit_observations],
            dtype=numpy.double)
        obs_weight = float(obs_weights.sum())

        obs_new_lat, obs_new_lon = numpy.average(
            obs_positions, axis=0, weights=obs_weights)
        obs_new_lat = float(obs_new_lat)
        obs_new_lon = float(obs_new_lon)

        obs_max_lat, obs_max_lon = obs_positions.max(axis=0)
        obs_min_lat, obs_min_lon = obs_positions.min(axis=0)
        obs_box_dist = distance(obs_min_lat, obs_min_lon,
                                obs_max_lat, obs_max_lon)

        if obs_box_dist > self.max_dist_meters:
            # the new observations are already too far apart
            if not shard_station:
                values.update({
                    'created': created,
                    'last_seen': None,
                    'modified': self.utcnow,
                    'block_first': self.today,
                    'block_last': self.today,
                    'block_count': 1,
                })
                return ('new_move', values)
            else:
                block_count = shard_station.block_count or 0
                values.update({
                    'last_seen': None,
                    'modified': self.utcnow,
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
                return ('move', values)

        if shard_station is None:
            # totally new station, only agreeing observations
            radius = circle_radius(
                obs_new_lat, obs_new_lon,
                obs_max_lat, obs_max_lon, obs_min_lat, obs_min_lon)
            values.update({
                'created': created,
                'last_seen': self.today,
                'modified': self.utcnow,
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
                    'last_seen': None,
                    'modified': self.utcnow,
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
                return ('move', values)
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
                    'last_seen': self.today,
                    'modified': self.utcnow,
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
                    'block_first': shard_station.block_first,
                    'block_last': shard_station.block_last,
                    'block_count': shard_station.block_count,
                })
                return ('change', values)

        return (None, None)  # pragma: no cover

    def _shard_observations(self, observations):
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

    def _query_shard(self, session, shard, keys):
        raise NotImplementedError()

    def _query_stations(self, session, shard, shard_values):
        blocklist = {}
        stations = {}

        keys = list(shard_values.keys())
        rows = self._query_shard(session, shard, keys)
        for row in rows:
            unique_key = row.unique_key
            stations[unique_key] = row
            blocklist[unique_key] = row.blocked(today=self.today)

        return (blocklist, stations)

    def _update_shard(self, session, shard, shard_values, stats_counter):
        updated_areas = set()
        new_data = defaultdict(list)
        blocklist, stations = self._query_stations(
            session, shard, shard_values)

        for station_key, observations in shard_values.items():
            # Count all observations.
            stats_counter['obs'] += len(observations)

            if blocklist.get(station_key, False):
                # Drop observations for blocklisted stations.
                continue

            status, result = self.station_values(
                station_key, stations.get(station_key, None), observations)

            if not status:
                continue

            new_data[status].append(result)

            if status in ('change', 'confirm'):
                stats_counter['confirm'] += 1
            if status in ('new', 'new_move'):
                stats_counter['new_station'] += 1
            if status in ('move', 'new_move'):
                stats_counter['block'] += 1

            # track potential updates to dependent areas
            self.add_area_update(updated_areas, station_key)

        if new_data['new']:
            # do a batch insert of new stations
            stmt = shard.__table__.insert(
                mysql_on_duplicate='samples = samples'  # no-op
            )
            session.execute(stmt.values(new_data['new']))

        if new_data['new_move']:
            # do a batch insert of new moving stations
            stmt = shard.__table__.insert(
                mysql_on_duplicate='block_count = block_count'  # no-op
            )
            session.execute(stmt.values(new_data['new_move']))

        if new_data['change'] or new_data['move']:
            # do a batch update of changing and moving stations
            session.bulk_update_mappings(
                shard, new_data['change'] + new_data['move'])

        if new_data['confirm']:
            # do a batch update of confirmed stations
            session.bulk_update_mappings(shard, new_data['confirm'])

        return updated_areas

    def _update_shards(self, session, sharded_obs):
        stats_counter = defaultdict(int)
        updated_areas = set()

        for shard, shard_values in sharded_obs.items():
            updated_areas.update(self._update_shard(
                session, shard, shard_values, stats_counter))

        return (updated_areas, stats_counter)

    def __call__(self):
        sharded_obs = self._shard_observations(self.data_queue.dequeue())
        if not sharded_obs:
            return

        success = False
        for i in range(self._retries):
            try:
                with self.task.db_session() as session:
                    updated_areas, stats_counter = \
                        self._update_shards(session, sharded_obs)
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


class BlueUpdater(StationUpdater):

    max_dist_meters = BLUE_MAX_RADIUS
    obs_model = BlueObservation
    queue_prefix = 'update_blue_'
    station_type = 'blue'
    stat_obs_key = StatKey.blue
    stat_station_key = StatKey.unique_blue

    def _base_key_values(self, station_key):
        return {
            'mac': station_key,
        }

    def _base_submit_values(self, station_key, shard_station, observations):
        return self._base_key_values(station_key)

    def _query_shard(self, session, shard, keys):
        return (session.query(shard)
                       .filter(shard.mac.in_(keys))).all()


class CellUpdater(StationUpdater):

    max_dist_meters = CELL_MAX_RADIUS
    obs_model = CellObservation
    queue_prefix = 'update_cell_'
    station_type = 'cell'
    stat_obs_key = StatKey.cell
    stat_station_key = StatKey.unique_cell

    def add_area_update(self, updated_areas, key):
        updated_areas.add(encode_cellarea(*decode_cellid(key)[:4]))

    def queue_area_updates(self, pipe, updated_areas):
        data_queue = self.data_queues['update_cellarea']
        data_queue.enqueue(list(updated_areas), pipe=pipe)

    def _base_key_values(self, station_key):
        radio, mcc, mnc, lac, cid = decode_cellid(station_key)
        return {
            'cellid': station_key,
            'radio': radio,
            'mcc': mcc,
            'mnc': mnc,
            'lac': lac,
            'cid': cid,
        }

    def _base_submit_values(self, station_key, shard_station, observations):
        values = self._base_key_values(station_key)

        psc = None
        if shard_station:
            psc = shard_station.psc

        if observations:
            pscs = [obs.psc for obs in observations if obs.psc is not None]
            if pscs:
                psc = pscs[-1]
        values['psc'] = psc
        return values

    def _query_shard(self, session, shard, keys):
        return (session.query(shard)
                       .filter(shard.cellid.in_(keys))).all()


class WifiUpdater(StationUpdater):

    max_dist_meters = WIFI_MAX_RADIUS
    obs_model = WifiObservation
    queue_prefix = 'update_wifi_'
    station_type = 'wifi'
    stat_obs_key = StatKey.wifi
    stat_station_key = StatKey.unique_wifi

    def _base_key_values(self, station_key):
        return {
            'mac': station_key,
        }

    def _base_submit_values(self, station_key, shard_station, observations):
        return self._base_key_values(station_key)

    def _query_shard(self, session, shard, keys):
        return (session.query(shard)
                       .filter(shard.mac.in_(keys))).all()
