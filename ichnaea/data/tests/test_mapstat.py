from datetime import timedelta

from ichnaea.data.tasks import update_mapstat
from ichnaea.models.content import (
    encode_datamap_grid,
    MapStat,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea import util


class TestMapStat(CeleryTestCase):

    def setUp(self):
        super(TestMapStat, self).setUp()
        self.queue = self.celery_app.data_queues['update_mapstat']
        self.today = util.utcnow().date()
        self.yesterday = self.today - timedelta(days=1)

    def _add(self, triples):
        for lat, lon, time in triples:
            lat, lon = MapStat.scale(lat, lon)
            self.session.add(MapStat(lat=lat, lon=lon, time=time))
        self.session.flush()

    def _check_position(self, stat, pair):
        lat, lon = pair
        lat, lon = MapStat.scale(lat, lon)
        self.assertEqual(stat.lat, lat)
        self.assertEqual(stat.lon, lon)

    def _queue(self, pairs):
        grids = []
        for lat, lon in pairs:
            grids.append(
                encode_datamap_grid(lat, lon, scale=True, codec='base64'))
        self.queue.enqueue(grids)

    def test_empty(self):
        update_mapstat.delay().get()
        self.assertEqual(self.session.query(MapStat).count(), 0)

    def test_one(self):
        self._queue([(1.234567, 2.345678)])
        update_mapstat.delay().get()

        stats = self.session.query(MapStat).all()
        self.assertEqual(len(stats), 1)
        self._check_position(stats[0], (1.235, 2.346))
        self.assertEqual(stats[0].time, self.today)

    def test_update(self):
        self._add([(1.0, 2.0, self.yesterday)])
        self._queue([(1.0, 2.0)])
        update_mapstat.delay().get()

        stats = self.session.query(MapStat).all()
        self.assertEqual(len(stats), 1)
        self._check_position(stats[0], (1.0, 2.0))
        self.assertEqual(stats[0].time, self.yesterday)

    def test_multiple(self):
        self._add([
            (1.0, 2.0, self.yesterday),
            (2.0, -3.0, self.today),
        ])
        self._queue([
            (1.0, 2.0),
            (1.0, 2.0),
            (2.0011, 3.0011),
            (2.0012, 3.0012),
            (2.0013, 3.0013),
            (0.0, 0.0),
            (1.0, 2.0),
            (1.00001, 2.00001),
        ])
        update_mapstat.delay(batch=2).get()

        stats = self.session.query(MapStat).all()
        self.assertEqual(len(stats), 4)
        positions = set()
        for stat in stats:
            positions.add((stat.lat / 1000.0, stat.lon / 1000.0))
        self.assertEqual(
            positions,
            set([(1.0, 2.0), (2.0, -3.0), (0.0, 0.0), (2.001, 3.001)]))

    def test_dict_queue(self):
        # BBB
        self._queue([(1.0, 2.0)])
        self.queue.enqueue([{'lat': 1.1, 'lon': 2.2}])
        self._queue([(1.2, 2.3)])
        update_mapstat.delay().get()

        stats = self.session.query(MapStat).all()
        self.assertEqual(len(stats), 3)
