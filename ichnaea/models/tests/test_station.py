from datetime import timedelta

from ichnaea.models.station import ScoreMixin
from ichnaea.tests.base import TestCase
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


class TestScoreMixin(TestCase):

    def test_score(self):
        now = util.utcnow()
        self.assertAlmostEqual(DummyModel(
            now, now, 0, 1).score(now), 0.05, 2)
        self.assertAlmostEqual(DummyModel(
            now - timedelta(days=1), now, 10, 2).score(now), 0.1, 2)
        self.assertAlmostEqual(DummyModel(
            now - timedelta(days=5), now, 10, 2).score(now), 0.5, 2)
        self.assertAlmostEqual(DummyModel(
            now - timedelta(days=10), now, 10, 2).score(now), 1.0, 2)
        self.assertAlmostEqual(DummyModel(
            now - timedelta(days=10), now, 10, 64).score(now), 6.0, 2)
        self.assertAlmostEqual(DummyModel(
            now - timedelta(days=10), now, 10, 1024).score(now), 10.0, 2)
        self.assertAlmostEqual(DummyModel(
            now - timedelta(days=10), now, 0, 1024).score(now), 0.5, 2)
        self.assertAlmostEqual(DummyModel(
            now - timedelta(days=70), now - timedelta(days=40),
            10, 1024).score(now), 7.07, 2)
        self.assertAlmostEqual(DummyModel(
            now - timedelta(days=190), now - timedelta(days=180),
            10, 1024).score(now), 3.78, 2)
        self.assertAlmostEqual(DummyModel(
            now - timedelta(days=190), now - timedelta(days=180),
            10, 64).score(now), 2.27, 2)

    def test_block_last(self):
        now = util.utcnow()
        self.assertAlmostEqual(DummyModel(
            now - timedelta(days=70),
            now - timedelta(days=60),
            10, 64,
            (now - timedelta(days=65)).date()).score(now), 1.73, 2)

    def test_last_seen(self):
        now = util.utcnow()
        self.assertAlmostEqual(DummyModel(
            now - timedelta(days=70),
            now - timedelta(days=60),
            10, 64,
            (now - timedelta(days=65)).date(),
            (now - timedelta(days=58)).date()).score(now), 2.42, 2)
