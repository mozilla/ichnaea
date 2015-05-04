from collections import defaultdict

from ichnaea.data.base import DataTask
from ichnaea.models.content import (
    Score,
)
from ichnaea import util


class ScoreUpdater(DataTask):

    def __init__(self, task, session, pipe):
        DataTask.__init__(self, task, session)
        self.pipe = pipe
        self.queue = self.task.app.data_queues['update_score']
        self.today = util.utcnow().date()

    def update(self, batch=1000):
        scores = defaultdict(int)
        for score in self.queue.dequeue(batch=batch):
            key = score['hashkey']
            if key.time is None:
                key.time = self.today
            scores[key] += score['value']

        for key, value in scores.items():
            Score.incr(self.session, key, value)

        if self.queue.size() >= batch:
            self.task.apply_async(
                kwargs={'batch': batch},
                countdown=1,
                expires=57)

        return len(scores)
