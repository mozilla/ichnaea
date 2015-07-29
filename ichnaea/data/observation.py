from collections import defaultdict

from sqlalchemy.orm import load_only

from ichnaea.constants import (
    PERMANENT_BLOCKLIST_THRESHOLD,
    TEMPORARY_BLOCKLIST_DURATION,
)
from ichnaea.data.base import DataTask
from ichnaea.models import (
    Cell,
    CellBlocklist,
    CellObservation,
    Score,
    ScoreKey,
    StatCounter,
    StatKey,
    Wifi,
    WifiBlocklist,
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
            first_blocklisted = None
            station = self.station_model.getkey(self.session, key)

            if station is None:
                # Drop observations for blocklisted stations.
                blocklisted, first_blocklisted = self.blocklisted_station(key)
                if blocklisted:
                    drop_counter['blocklisted'] += len(observations)
                    continue

                if not first_blocklisted:
                    # We discovered an actual new complete station.
                    new_stations += 1

            # TODO: station creation happens too early
            if observations:
                all_observations.extend(observations)
                self.create_station(station, key, first_blocklisted)

        added = len(all_observations)
        self.emit_stats(added, drop_counter)
        self.emit_statcounters(added, new_stations)
        self.queue_scores(userid, new_stations)

        return all_observations

    def blocklisted_station(self, key):
        query = (self.blocklist_model.querykey(self.session, key)
                                     .options(load_only('count', 'time')))
        block = query.first()
        if block is not None:
            age = self.utcnow - block.time
            temp_blocklisted = age < TEMPORARY_BLOCKLIST_DURATION
            perm_blocklisted = block.count >= PERMANENT_BLOCKLIST_THRESHOLD
            if temp_blocklisted or perm_blocklisted:
                return (True, block.time)
            return (False, block.time)
        return (False, None)

    def create_station(self, station, key, first_blocklisted):
        if station is None:
            created = self.utcnow
            if first_blocklisted:
                # if the station did previously exist, retain at least the
                # time it was first put on a blocklist as the creation date
                created = first_blocklisted
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
    blocklist_model = CellBlocklist
    queue_name = 'update_cell'


class WifiObservationQueue(ObservationQueue):

    stat_obs_key = StatKey.wifi
    stat_station_key = StatKey.unique_wifi
    station_score = ScoreKey.new_wifi
    station_type = 'wifi'
    station_model = Wifi
    observation_model = WifiObservation
    blocklist_model = WifiBlocklist
    queue_name = 'update_wifi'
