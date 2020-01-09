from datetime import timedelta

from sqlalchemy import delete, select

from ichnaea.db import retry_on_mysql_lock_fail
from ichnaea.models.content import DataMap, encode_datamap_grid
from ichnaea import util


class DataMapCleaner(object):
    def __init__(self, task, shard_id=None):
        self.task = task
        self.shard_id = shard_id
        self.shard = DataMap.shards().get(shard_id)

    def _cleanup_shards(self, session):
        today = util.utcnow().date()
        one_year = today - timedelta(days=365)

        table = self.shard.__table__
        result = session.execute(delete(table).where(table.c.modified < one_year))
        return result

    def __call__(self):
        deleted_rows = 0
        with self.task.db_session() as session:
            deleted_rows = self._cleanup_shards(session)
        return deleted_rows


class DataMapUpdater(object):
    def __init__(self, task, shard_id=None):
        self.task = task
        self.shard_id = shard_id
        self.shard = DataMap.shards().get(shard_id)
        self.shard_table = self.shard.__table__

    @retry_on_mysql_lock_fail(metric="datamaps.dberror")
    def _update_shards(self, grids):
        with self.task.db_session() as session:
            self._update_shards_with_session(session, grids)

    def _update_shards_with_session(self, session, grids):
        today = util.utcnow().date()

        rows = session.execute(
            select([self.shard_table.c.grid, self.shard_table.c.modified])
            .where(self.shard_table.c.grid.in_(grids))
            .with_for_update()
        ).fetchall()

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
                update_values.append({"grid": grid, "modified": today})
            else:
                new_values.append({"grid": grid, "created": today, "modified": today})

        if new_values:
            # do a batch insert of new grids
            session.execute(
                self.shard.__table__.insert().values(new_values)
                # If there was an unexpected insert, log warning instead of error
                .prefix_with("IGNORE", dialect="mysql")
            )

        if update_values:
            # do a batch update of grids
            session.bulk_update_mappings(self.shard, update_values)

    def __call__(self):
        queue = self.task.app.data_queues["update_datamap_" + self.shard_id]
        grids = queue.dequeue()
        grids = list(set(grids))
        if not grids or not self.shard:
            return 0

        self._update_shards(grids)

        if queue.ready():
            self.task.apply_countdown(kwargs={"shard_id": self.shard_id})

        return len(grids)
