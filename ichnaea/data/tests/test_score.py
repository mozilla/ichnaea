from datetime import timedelta

from ichnaea.data.tasks import update_score
from ichnaea.models.content import (
    Score,
    ScoreKey,
    User,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea import util


class TestScore(CeleryTestCase):

    def setUp(self):
        super(TestScore, self).setUp()
        self.queue = self.celery_app.data_queues['update_score']
        self.today = util.utcnow().date()
        self.yesterday = self.today - timedelta(days=1)

    def _add_nicks(self, names):
        users = {}
        for name in names:
            users[name] = user = User(nickname=name)
            self.session.add(user)
        self.session.flush()
        return users

    def _add(self, quads):
        for userid, key, time, value in quads:
            self.session.add(Score(
                userid=userid, key=key, time=time, value=value))
        self.session.flush()

    def _queue(self, triples):
        scores = [{'userid': userid, 'key': key, 'value': value} for
                  userid, key, value in triples]
        self.queue.enqueue(scores)

    def test_empty(self):
        update_score.delay().get()
        self.assertEqual(self.session.query(Score).count(), 0)

    def test_one(self):
        users = self._add_nicks([u'nick1'])
        self._queue([(users[u'nick1'].id, ScoreKey.location, 3)])
        update_score.delay().get()

        scores = self.session.query(Score).all()
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].userid, users[u'nick1'].id)
        self.assertEqual(scores[0].key, ScoreKey.location)
        self.assertEqual(scores[0].time, self.today)
        self.assertEqual(scores[0].value, 3)

    def test_update(self):
        users = self._add_nicks([u'nick1'])
        self._add([(users[u'nick1'].id, ScoreKey.location, self.today, 2)])
        self._queue([(users[u'nick1'].id, ScoreKey.location, 3)])
        update_score.delay().get()

        scores = self.session.query(Score).all()
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].value, 5)

    def test_multiple(self):
        users = self._add_nicks([u'nick1', u'nick2'])
        self._add([
            (users['nick1'].id, ScoreKey.location, self.yesterday, 20),
            (users['nick1'].id, ScoreKey.location, self.today, 2),
            (users['nick1'].id, ScoreKey.new_wifi, self.today, 4),
            (users['nick2'].id, ScoreKey.location, self.today, 7),
            (users['nick2'].id, ScoreKey.new_cell, self.today, 12),
        ])
        self._queue([
            (users['nick2'].id, ScoreKey.location, 4),
            (users['nick1'].id, ScoreKey.location, 1),
            (users['nick1'].id, ScoreKey.location, 1),
            (users['nick1'].id, ScoreKey.new_wifi, 2),
            (users['nick1'].id, ScoreKey.new_cell, 3),
            (users['nick2'].id, ScoreKey.new_cell, 1),
        ])

        update_score.delay(batch=3).get()
        scores = (self.session.query(Score)
                              .filter(Score.time == self.today)).all()
        self.assertEqual(len(scores), 5)

        grouped = {}
        for score in scores:
            grouped[(score.userid, score.key)] = score.value

        self.assertEqual(grouped, {
            (users['nick1'].id, ScoreKey.location): 4,
            (users['nick1'].id, ScoreKey.new_cell): 3,
            (users['nick1'].id, ScoreKey.new_wifi): 6,
            (users['nick2'].id, ScoreKey.location): 11,
            (users['nick2'].id, ScoreKey.new_cell): 13,
        })

    def test_hashkey(self):
        # BBB
        from ichnaea.models.content import ScoreHashKey

        users = self._add_nicks([u'nick1', u'nick2'])
        self._add([
            (users['nick1'].id, ScoreKey.location, self.yesterday, 20),
            (users['nick1'].id, ScoreKey.location, self.today, 2),
            (users['nick1'].id, ScoreKey.new_wifi, self.today, 4),
            (users['nick2'].id, ScoreKey.location, self.today, 7),
            (users['nick2'].id, ScoreKey.new_cell, self.today, 12),
        ])
        triples = [
            (users['nick2'].id, ScoreKey.location, 4),
            (users['nick1'].id, ScoreKey.location, 1),
            (users['nick1'].id, ScoreKey.location, 1),
            (users['nick1'].id, ScoreKey.new_wifi, 2),
            (users['nick1'].id, ScoreKey.new_cell, 3),
            (users['nick2'].id, ScoreKey.new_cell, 1),
        ]
        self.queue.enqueue([{
            'hashkey': ScoreHashKey(userid=userid, key=key, time=None),
            'value': value} for userid, key, value in triples])

        update_score.delay(batch=3).get()
        scores = (self.session.query(Score)
                              .filter(Score.time == self.today)).all()
        self.assertEqual(len(scores), 5)

        grouped = {}
        for score in scores:
            grouped[(score.userid, score.key)] = score.value

        self.assertEqual(grouped, {
            (users['nick1'].id, ScoreKey.location): 4,
            (users['nick1'].id, ScoreKey.new_cell): 3,
            (users['nick1'].id, ScoreKey.new_wifi): 6,
            (users['nick2'].id, ScoreKey.location): 11,
            (users['nick2'].id, ScoreKey.new_cell): 13,
        })
