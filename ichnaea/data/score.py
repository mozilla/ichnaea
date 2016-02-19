from collections import defaultdict

from sqlalchemy.orm import load_only

from ichnaea.models.content import (
    Score,
)
from ichnaea import util


class ScoreUpdater(object):

    def __init__(self, task, pipe):
        self.task = task
        self.pipe = pipe
        self.queue = self.task.app.data_queues['update_score']
        self.today = util.utcnow().date()

    def _update_scores(self, session, score_values):
        score_iter = Score.iterkeys(
            session, list(score_values.keys()),
            extra=lambda query: query.options(load_only('value', )))

        scores = {}
        for score in score_iter:
            scores[score.hashkey()] = score

        for key, value in score_values.items():
            score = scores.get(key, None)
            value = int(value)
            if score is not None:
                score.value += value
            else:
                stmt = Score.__table__.insert(
                    mysql_on_duplicate='value = value + %s' % value
                ).values(value=value, **key.__dict__)
                session.execute(stmt)

        return len(scores)

    def __call__(self, batch=1000):
        score_values = defaultdict(int)
        for score in self.queue.dequeue(batch=batch):
            key = score['hashkey']
            if key.time is None:
                key.time = self.today
            score_values[key] += score['value']

        with self.task.db_session() as session:
            length = self._update_scores(session, score_values)

        if self.queue.enough_data(batch=batch):
            self.task.apply_async(
                kwargs={'batch': batch},
                countdown=2,
                expires=10)

        return length
