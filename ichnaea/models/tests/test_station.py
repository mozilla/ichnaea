from datetime import timedelta

from ichnaea.models.station import ScoreMixin
from ichnaea.tests.base import TestCase
from ichnaea import util


class DummyModel(ScoreMixin):

    def __init__(self, created, modified, radius, samples):
        self.created = created
        self.modified = modified
        self.radius = radius
        self.samples = samples


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
