from sqlalchemy.orm import load_only

from ichnaea.models.content import (
    DataMap,
    encode_datamap_grid,
)
from ichnaea import util


class DataMapUpdater(object):

    def __init__(self, task, pipe, shard_id=None):
        self.task = task
        self.pipe = pipe
        self.shard_id = shard_id
        self.shard = DataMap.shards().get(shard_id)

    def _update_shards(self, session, grids):
        today = util.utcnow().date()

        load_fields = ('grid', 'modified')
        rows = (session.query(self.shard)
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
            session.execute(stmt.values(new_values))

        if update_values:
            # do a batch update of grids
            session.bulk_update_mappings(self.shard, update_values)

    def __call__(self):
        queue = self.task.app.data_queues['update_datamap_' + self.shard_id]
        grids = queue.dequeue()
        grids = list(set(grids))
        if not grids or not self.shard:
            return 0

        with self.task.db_session() as session:
            self._update_shards(session, grids)

        if queue.ready():  # pragma: no cover
            self.task.apply_countdown(kwargs={'shard_id': self.shard_id})

        return len(grids)
