from datetime import timedelta

from ichnaea.api.locate.score import (
    area_score,
    station_score,
)
from ichnaea import util


class Dummy(object):

    def __init__(self, created, modified, radius, samples,
                 block_last=None, last_seen=None):
        self.created = created
        self.modified = modified
        self.radius = radius
        self.samples = samples
        self.block_last = block_last
        self.last_seen = last_seen


class AreaDummy(object):

    def __init__(self, created, modified, radius, num_cells,
                 last_seen=None):
        self.created = created
        self.modified = modified
        self.radius = radius
        self.num_cells = num_cells
        self.last_seen = last_seen


class TestScore(object):

    def test_score(self):
        now = util.utcnow()
        assert round(station_score(Dummy(
            now, now, 0, 1), now), 2) == 0.05
        assert round(station_score(Dummy(
            now - timedelta(days=1), now, 10, 2), now), 2) == 0.1
        assert round(station_score(Dummy(
            now - timedelta(days=5), now, 10, 2), now), 2) == 0.5
        assert round(station_score(Dummy(
            now - timedelta(days=10), now, 10, 2), now), 2) == 1.0
        assert round(station_score(Dummy(
            now - timedelta(days=10), now, 10, 64), now), 2) == 6.0
        assert round(station_score(Dummy(
            now - timedelta(days=10), now, 10, 1024), now), 2) == 10.0
        assert round(station_score(Dummy(
            now - timedelta(days=10), now, 0, 1024), now), 2) == 0.5
        assert round(station_score(Dummy(
            now - timedelta(days=70), now - timedelta(days=40),
            10, 1024), now), 2) == 7.07
        assert round(station_score(Dummy(
            now - timedelta(days=190), now - timedelta(days=180),
            10, 1024), now), 2) == 3.78
        assert round(station_score(Dummy(
            now - timedelta(days=190), now - timedelta(days=180),
            10, 64), now), 2) == 2.27

    def test_block_last(self):
        now = util.utcnow()
        assert round(station_score(Dummy(
            now - timedelta(days=70),
            now - timedelta(days=60),
            10, 64,
            (now - timedelta(days=65)).date()), now), 2) == 1.73

    def test_last_seen(self):
        now = util.utcnow()
        assert round(station_score(Dummy(
            now - timedelta(days=70),
            now - timedelta(days=60),
            10, 64,
            (now - timedelta(days=65)).date(),
            (now - timedelta(days=58)).date()), now), 2) == 2.42

    def test_score_area(self):
        now = util.utcnow()
        area = AreaDummy(created=now, modified=now, radius=10, num_cells=4)
        assert round(area_score(area, now), 2) == 0.2
        area = AreaDummy(created=now, modified=now, radius=0, num_cells=100)
        assert round(area_score(area, now), 2) == 0.1
