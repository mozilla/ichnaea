from sqlalchemy.orm import load_only

from ichnaea.data.base import DataTask
from ichnaea.models.content import (
    DATAMAP_SHARDS,
    encode_datamap_grid,
)
from ichnaea import util


class DataMapUpdater(DataTask):

    def __init__(self, task, session, pipe, shard_id=None):
        DataTask.__init__(self, task, session)
        self.pipe = pipe
        self.shard_id = shard_id
        self.shard = DATAMAP_SHARDS.get(shard_id)

    def __call__(self, batch=1000):
        queue = self.task.app.data_queues['update_datamap_' + self.shard_id]
        today = util.utcnow().date()
        grids = queue.dequeue(batch=batch, json=False)
        grids = list(set(grids))
        if not grids or not self.shard:
            return 0

        load_fields = ('grid', 'modified')
        rows = (self.session.query(self.shard)
                            .filter(self.shard.grid.in_(grids))
                            .options(load_only(*load_fields))).all()

        outdated = set()
        skip = set()
        for row in rows:
            grid = encode_datamap_grid(*row.grid)
            if row.modified == today:
                skip.add(grid)
            else:
                outdated.add(grid)

        new_values = []
        update_values = []
        for grid in grids:
            if grid in skip:
                continue
            elif grid in outdated:
                update_values.append(
                    {'grid': grid, 'modified': today})
            else:
                new_values.append(
                    {'grid': grid, 'created': today, 'modified': today})

        if new_values:
            # do a batch insert of new grids
            stmt = self.shard.__table__.insert(
                mysql_on_duplicate='modified = modified'  # no-op
            )
            self.session.execute(stmt.values(new_values))

        if update_values:
            # do a batch update of grids
            self.session.bulk_update_mappings(self.shard, update_values)

        if queue.enough_data(batch=batch):
            self.task.apply_async(
                kwargs={'batch': batch, 'shard_id': self.shard_id},
                countdown=2,
                expires=10)

        return len(grids)
