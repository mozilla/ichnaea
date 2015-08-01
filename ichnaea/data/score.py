from collections import defaultdict

from sqlalchemy.orm import load_only

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
        score_values = defaultdict(int)
        for score in self.queue.dequeue(batch=batch):
            key = score['hashkey']
            if key.time is None:
                key.time = self.today
            score_values[key] += score['value']

        score_iter = Score.iterkeys(
            self.session, list(score_values.keys()),
            extra=lambda query: query.options(load_only('value', )))

        scores = {}
        for score in score_iter:
            scores[score.hashkey()] = score

        for key, value in score_values.items():
            score = scores.get(key, None)
            if score is not None:
                score.value += int(value)
            else:
                stmt = Score.__table__.insert(
                    on_duplicate='value = value + %s' % int(value)).values(
                    value=value, **key.__dict__)
                self.session.execute(stmt)

        if self.queue.size() >= batch:
            self.task.apply_async(
                kwargs={'batch': batch},
                countdown=2,
                expires=10)

        return len(scores)
