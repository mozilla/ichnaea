from ichnaea.data.base import DataTask
from ichnaea.models import (
    CellObservation,
    WifiObservation,
)


class ObservationQueue(DataTask):

    queue_name = None

    def __init__(self, task, session, pipe):
        DataTask.__init__(self, task, session)
        self.pipe = pipe
        self.data_queue = self.task.app.data_queues[self.queue_name]

    def insert(self, entries):
        all_observations = []

        for entry in entries:
            if isinstance(entry, self.observation_model):
                obs = entry
            elif isinstance(entry, dict):  # pragma: no cover
                obs = self.observation_model.create(**entry)
                if not obs:
                    continue
            else:  # pragma: no cover
                continue

            all_observations.append(obs)

        self.data_queue.enqueue(all_observations, pipe=self.pipe)
        return len(all_observations)


class CellObservationQueue(ObservationQueue):

    station_type = 'cell'
    observation_model = CellObservation
    queue_name = 'update_cell'


class WifiObservationQueue(ObservationQueue):

    station_type = 'wifi'
    observation_model = WifiObservation
    queue_name = 'update_wifi'
