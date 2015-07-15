from collections import defaultdict

from sqlalchemy.orm import load_only

from ichnaea.constants import (
    PERMANENT_BLACKLIST_THRESHOLD,
    TEMPORARY_BLACKLIST_DURATION,
)
from ichnaea.data.base import DataTask
from ichnaea.models import (
    Cell,
    CellBlacklist,
    CellObservation,
    Score,
    ScoreKey,
    StatCounter,
    StatKey,
    Wifi,
    WifiBlacklist,
    WifiObservation,
)
from ichnaea import util


class ObservationQueue(DataTask):

    queue_name = None

    def __init__(self, task, session, pipe, utcnow=None):
        DataTask.__init__(self, task, session)
        self.pipe = pipe
        self.data_queue = self.task.app.data_queues[self.queue_name]
        if utcnow is None:
            utcnow = util.utcnow()
        self.utcnow = utcnow

    def stat_count(self, action, what, count):
        if count != 0:
            self.stats_client.incr(
                'items.{action}.{station_type}_{what}'.format(
                    action=action, station_type=self.station_type, what=what),
                count)

    def emit_stats(self, added, dropped):
        self.stat_count('inserted', 'observations', added)
        for name, count in dropped.items():
            self.stat_count('dropped', 'ingress_' + name, dropped[name])

    def emit_statcounters(self, obs, stations):
        day = self.utcnow.date()
        StatCounter(self.stat_obs_key, day).incr(self.pipe, obs)
        StatCounter(self.stat_station_key, day).incr(self.pipe, stations)

    def queue_scores(self, userid, new_stations):
        # Credit the user with discovering any new stations.
        if userid is None or new_stations <= 0:
            return

        queue = self.task.app.data_queues['update_score']
        key = Score.to_hashkey(
            userid=userid, key=self.station_score, time=None)
        queue.enqueue([{'hashkey': key, 'value': int(new_stations)}])

    def insert(self, entries, userid=None):
        all_observations = self._insert(entries, userid=userid)
        self.data_queue.enqueue(all_observations, pipe=self.pipe)
        return len(all_observations)

    def _insert(self, entries, userid=None):
        all_observations = []
        drop_counter = defaultdict(int)
        new_stations = 0

        # Process entries and group by validated station key
        station_observations = defaultdict(list)
        for entry in entries:
            obs = self.observation_model.create(**entry)
            if not obs:
                drop_counter['malformed'] += 1
                continue

            station_observations[obs.hashkey()].append(obs)

        # Process observations one station at a time
        for key, observations in station_observations.items():
            first_blacklisted = None
            incomplete = False
            station = self.station_model.getkey(self.session, key)

            if station is None:
                # Drop observations for blacklisted stations.
                blacklisted, first_blacklisted = self.blacklisted_station(key)
                if blacklisted:
                    drop_counter['blacklisted'] += len(observations)
                    continue

                incomplete = self.incomplete_observation(key)
                if not incomplete and not first_blacklisted:
                    # We discovered an actual new complete station.
                    new_stations += 1

            # Don't make stations for incomplete observations
            # and don't queue their data for processing
            # TODO: station creation happens too early
            if not incomplete and observations:
                all_observations.extend(observations)
                self.create_station(station, key, first_blacklisted)

        added = len(all_observations)
        self.emit_stats(added, drop_counter)
        self.emit_statcounters(added, new_stations)
        self.queue_scores(userid, new_stations)

        return all_observations

    def blacklisted_station(self, key):
        query = (self.blacklist_model.querykey(self.session, key)
                                     .options(load_only('count', 'time')))
        black = query.first()
        if black is not None:
            age = self.utcnow - black.time
            temp_blacklisted = age < TEMPORARY_BLACKLIST_DURATION
            perm_blacklisted = black.count >= PERMANENT_BLACKLIST_THRESHOLD
            if temp_blacklisted or perm_blacklisted:
                return (True, black.time)
            return (False, black.time)
        return (False, None)

    def incomplete_observation(self, key):
        return False

    def create_station(self, station, key, first_blacklisted):
        if station is None:
            created = self.utcnow
            if first_blacklisted:
                # if the station did previously exist, retain at least the
                # time it was first put on a blacklist as the creation date
                created = first_blacklisted
            stmt = self.station_model.__table__.insert(
                on_duplicate='total_measures = total_measures'  # no-op change
            ).values(
                created=created,
                modified=self.utcnow,
                range=0,
                total_measures=0,
                **key.__dict__)
            self.session.execute(stmt)


class CellObservationQueue(ObservationQueue):

    stat_obs_key = StatKey.cell
    stat_station_key = StatKey.unique_cell
    station_score = ScoreKey.new_cell
    station_type = 'cell'
    station_model = Cell
    observation_model = CellObservation
    blacklist_model = CellBlacklist
    queue_name = 'update_cell'

    def incomplete_observation(self, key):
        # We want to store certain incomplete observations
        # even though they should not lead to the creation of a station
        # entry; these are cell observations with a missing value for
        # LAC and/or CID, and will be inferred from neighboring cells.
        for field in ('radio', 'mcc', 'mnc', 'lac', 'cid'):
            if getattr(key, field, None) is None:
                return True
        return False


class WifiObservationQueue(ObservationQueue):

    stat_obs_key = StatKey.wifi
    stat_station_key = StatKey.unique_wifi
    station_score = ScoreKey.new_wifi
    station_type = 'wifi'
    station_model = Wifi
    observation_model = WifiObservation
    blacklist_model = WifiBlacklist
    queue_name = 'update_wifi'
