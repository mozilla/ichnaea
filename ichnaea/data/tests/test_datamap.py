from collections import defaultdict
from datetime import timedelta

from ichnaea.data.tasks import update_datamap
from ichnaea.models.content import (
    DataMap,
    encode_datamap_grid,
)
from ichnaea import util


class TestDataMap(object):

    @property
    def today(self):
        return util.utcnow().date()

    @property
    def yesterday(self):
        return self.today - timedelta(days=1)

    def _add(self, session, entries):
        for lat, lon, time in entries:
            lat, lon = DataMap.scale(lat, lon)
            session.add(DataMap.shard_model(lat, lon)(
                grid=(lat, lon), created=time, modified=time))
        session.flush()

    def _check_position(self, stat, lat, lon):
        assert stat.grid == DataMap.scale(lat, lon)

    def _queue(self, celery, pairs):
        grids = defaultdict(list)
        for lat, lon in pairs:
            lat, lon = DataMap.scale(lat, lon)
            shard_id = DataMap.shard_id(lat, lon)
            grids[shard_id].append(encode_datamap_grid(lat, lon))

        for shard_id, values in grids.items():
            queue = celery.data_queues['update_datamap_' + shard_id]
            queue.enqueue(list(values))

    def test_empty(self, celery, session):
        for shard_id, shard in DataMap.shards().items():
            update_datamap.delay(shard_id=shard_id).get()
            assert session.query(shard).count() == 0

    def test_one(self, celery, session):
        lat = 1.234567
        lon = 2.345678
        shard_id = DataMap.shard_id(*DataMap.scale(lat, lon))
        self._queue(celery, [(lat, lon)])
        update_datamap.delay(shard_id=shard_id).get()

        grids = session.query(DataMap.shards()[shard_id]).all()
        assert len(grids) == 1
        self._check_position(grids[0], 1.235, 2.346)
        assert grids[0].created == self.today
        assert grids[0].modified == self.today

    def test_update(self, celery, session):
        lat = 1.0
        lon = 2.0
        shard_id = DataMap.shard_id(*DataMap.scale(lat, lon))
        self._add(session, [(lat, lon, self.yesterday)])
        self._queue(celery, [(lat, lon)])
        update_datamap.delay(shard_id=shard_id).get()

        grids = session.query(DataMap.shards()[shard_id]).all()
        assert len(grids) == 1
        self._check_position(grids[0], 1.0, 2.0)
        assert grids[0].created == self.yesterday
        assert grids[0].modified == self.today

    def test_multiple(self, celery, session):
        self._add(session, [
            (0.0, 1.0, self.today),
            (1.0, 2.0, self.yesterday),
            (-10.0, 40.0, self.yesterday),
        ])
        self._queue(celery, [
            (0.0, 1.0),
            (1.0, 2.0), (1.0, 2.0),
            (40.0011, 3.0011), (40.0012, 3.0012), (40.0013, 3.0013),
            (0.0, 0.0),
            (1.0, 2.0),
            (1.00001, 2.00001),
        ])
        for shard_id in DataMap.shards():
            update_datamap.delay(shard_id=shard_id).get()

        rows = []
        for shard in DataMap.shards().values():
            rows.extend(session.query(shard).all())

        assert len(rows) == 5
        created = set()
        modified = set()
        positions = set()
        for row in rows:
            lat, lon = row.grid
            created.add(row.created)
            modified.add(row.modified)
            positions.add((lat / 1000.0, lon / 1000.0))

        assert created == set([self.today, self.yesterday])
        assert modified == set([self.today, self.yesterday])
        assert (positions == set([
            (0.0, 0.0), (0.0, 1.0), (1.0, 2.0),
            (-10.0, 40.0), (40.001, 3.001)]))
