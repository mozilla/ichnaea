from datetime import timedelta

from ichnaea.models.station import ScoreMixin
from ichnaea import util


class DummyModel(ScoreMixin):

    def __init__(self, created, modified, radius, samples,
                 block_last=None, last_seen=None):
        self.created = created
        self.modified = modified
        self.radius = radius
        self.samples = samples
        self.block_last = block_last
        self.last_seen = last_seen


class TestScoreMixin(object):

    def test_score(self):
        now = util.utcnow()
        assert round(DummyModel(
            now, now, 0, 1).score(now), 2) == 0.05
        assert round(DummyModel(
            now - timedelta(days=1), now, 10, 2).score(now), 2) == 0.1
        assert round(DummyModel(
            now - timedelta(days=5), now, 10, 2).score(now), 2) == 0.5
        assert round(DummyModel(
            now - timedelta(days=10), now, 10, 2).score(now), 2) == 1.0
        assert round(DummyModel(
            now - timedelta(days=10), now, 10, 64).score(now), 2) == 6.0
        assert round(DummyModel(
            now - timedelta(days=10), now, 10, 1024).score(now), 2) == 10.0
        assert round(DummyModel(
            now - timedelta(days=10), now, 0, 1024).score(now), 2) == 0.5
        assert round(DummyModel(
            now - timedelta(days=70), now - timedelta(days=40),
            10, 1024).score(now), 2) == 7.07
        assert round(DummyModel(
            now - timedelta(days=190), now - timedelta(days=180),
            10, 1024).score(now), 2) == 3.78
        assert round(DummyModel(
            now - timedelta(days=190), now - timedelta(days=180),
            10, 64).score(now), 2) == 2.27

    def test_block_last(self):
        now = util.utcnow()
        assert round(DummyModel(
            now - timedelta(days=70),
            now - timedelta(days=60),
            10, 64,
            (now - timedelta(days=65)).date()).score(now), 2) == 1.73

    def test_last_seen(self):
        now = util.utcnow()
        assert round(DummyModel(
            now - timedelta(days=70),
            now - timedelta(days=60),
            10, 64,
            (now - timedelta(days=65)).date(),
            (now - timedelta(days=58)).date()).score(now), 2) == 2.42
