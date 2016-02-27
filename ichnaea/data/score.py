from collections import defaultdict

from ichnaea.models.content import (
    Score,
    ScoreKey,
)
from ichnaea import util


class ScoreUpdater(object):

    def __init__(self, task, pipe):
        self.task = task
        self.pipe = pipe
        self.queue = self.task.app.data_queues['update_score']

    def _update_scores(self, session, score_values):
        time = util.utcnow().date()
        for (key, userid), value in score_values.items():
            row = (session.query(Score)
                          .filter((Score.key == key),
                                  (Score.userid == userid),
                                  (Score.time == time))).first()

            if row is not None:
                row.value += value
            else:
                stmt = Score.__table__.insert(
                    mysql_on_duplicate='value = value + %s' % value
                ).values(key=key, userid=userid, time=time, value=value)
                session.execute(stmt)

    def __call__(self, batch=1000):
        score_values = defaultdict(int)
        for score in self.queue.dequeue(batch=batch):
            if 'hashkey' in score:
                # BBB
                hashkey = score['hashkey']
                key = hashkey.key
                userid = hashkey.userid
            else:
                key = ScoreKey(score['key'])
                userid = score['userid']

            score_values[(key, userid)] += score['value']

        with self.task.db_session() as session:
            self._update_scores(session, score_values)

        if self.queue.enough_data(batch=batch):
            self.task.apply_async(
                kwargs={'batch': batch},
                countdown=2,
                expires=10)
