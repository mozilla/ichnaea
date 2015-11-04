from datetime import timedelta

from ichnaea.data.mapstat import encode_mapstat_grid
from ichnaea.data.tasks import update_mapstat
from ichnaea.models.content import (
    DataMap,
    DATAMAP_SHARDS,
    decode_datamap_grid,
    encode_datamap_grid,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea import util


class TestMapStat(CeleryTestCase):  # BBB

    def setUp(self):
        super(TestMapStat, self).setUp()
        self.queue = self.celery_app.data_queues['update_mapstat']
        self.today = util.utcnow().date()
        self.yesterday = self.today - timedelta(days=1)

    def _queue(self, pairs):
        grids = []
        for lat, lon in pairs:
            grids.append(
                encode_mapstat_grid(lat, lon, scale=True))
        self.queue.enqueue(grids, json=False)

    def test_empty(self):
        update_mapstat.delay().get()
        for shard_id in DATAMAP_SHARDS:
            queue = self.celery_app.data_queues['update_datamap_' + shard_id]
            self.assertEqual(queue.size(), 0)

    def test_one(self):
        lat = 1.234567
        lon = 2.345678
        shard_id = DataMap.shard_id(*DataMap.scale(lat, lon))
        self._queue([(1.234567, 2.345678)])
        update_mapstat.delay().get()

        queue = self.celery_app.data_queues['update_datamap_' + shard_id]
        grids = queue.dequeue(batch=100, json=False)
        self.assertEqual(len(grids), 1)
        self.assertEqual(grids[0], encode_datamap_grid(lat, lon, scale=True))

    def test_multiple(self):
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

        positions = set()
        for shard_id in DATAMAP_SHARDS:
            queue = self.celery_app.data_queues['update_datamap_' + shard_id]
            grids = queue.dequeue(batch=100, json=False)
            for grid in grids:
                positions.add(decode_datamap_grid(grid, scale=True))

        self.assertEqual(len(positions), 3)
        self.assertEqual(
            positions,
            set([(1.0, 2.0), (0.0, 0.0), (2.001, 3.001)]))
