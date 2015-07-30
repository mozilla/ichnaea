from collections import defaultdict

from ichnaea.data.base import DataTask
from ichnaea.models import (
    Cell,
    CellBlocklist,
    CellObservation,
    Score,
    ScoreKey,
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

    def queue_scores(self, userid, new_stations):
        # Credit the user with discovering any new stations.
        if userid is None or new_stations <= 0:
            return

        queue = self.task.app.data_queues['update_score']
        key = Score.to_hashkey(
            userid=userid, key=self.station_score, time=None)
        queue.enqueue([{'hashkey': key, 'value': int(new_stations)}])

    def known_station(self, station_key):
        query = self.blocklist_model.querykey(self.session, station_key)
        return bool(query.count())

    def insert(self, entries, userid=None):
        all_observations = self._insert(entries, userid=userid)
        self.data_queue.enqueue(all_observations, pipe=self.pipe)
        return len(all_observations)

    def _insert(self, entries, userid=None):
        all_observations = []
        new_stations = 0

        # Process entries and group by validated station key
        station_observations = defaultdict(list)
        for entry in entries:
            obs = self.observation_model.create(**entry)
            if not obs:
                continue

            station_observations[obs.hashkey()].append(obs)

        # Process observations one station at a time
        for key, observations in station_observations.items():
            station = self.station_model.getkey(self.session, key)
            if station is None and not self.known_station(key):
                # We discovered an actual new complete station.
                new_stations += 1

            if observations:
                all_observations.extend(observations)

        self.queue_scores(userid, new_stations)

        return all_observations


class CellObservationQueue(ObservationQueue):

    station_score = ScoreKey.new_cell
    station_type = 'cell'
    station_model = Cell
    observation_model = CellObservation
    blocklist_model = CellBlocklist
    queue_name = 'update_cell'


class WifiObservationQueue(ObservationQueue):

    station_score = ScoreKey.new_wifi
    station_type = 'wifi'
    station_model = Wifi
    observation_model = WifiObservation
    blocklist_model = WifiBlocklist
    queue_name = 'update_wifi'
