from sqlalchemy.orm import load_only

from ichnaea.data.base import DataTask
from ichnaea.models.content import (
    decode_datamap_grid,
    MapStat,
)
from ichnaea import util


class MapStatUpdater(DataTask):

    def __init__(self, task, session, pipe):
        DataTask.__init__(self, task, session)
        self.pipe = pipe

    def __call__(self, batch=1000):
        queue = self.task.app.data_queues['update_mapstat']
        today = util.utcnow().date()
        positions = queue.dequeue(batch=batch)
        if not positions:
            return 0

        scaled_positions = set()
        for position in positions:
            lat, lon = decode_datamap_grid(position, codec='base64')
            scaled_positions.add((lat, lon))

        wanted = set()
        for scaled in scaled_positions:
            wanted.add(MapStat.to_hashkey(lat=scaled[0], lon=scaled[1]))

        stat_iter = MapStat.iterkeys(
            self.session, list(wanted),
            extra=lambda query: query.options(load_only('lat', 'lon')))

        found = set([stat.hashkey() for stat in stat_iter])

        new_stat_values = []
        for key in (wanted - found):
            new_stat_values.append({
                'lat': key.lat,
                'lon': key.lon,
                'time': today,
            })

        if new_stat_values:
            # do a batch insert of new stats
            stmt = MapStat.__table__.insert(
                mysql_on_duplicate='id = id'  # no-op
            )
            # but limit the batch depending on the model
            ins_batch = MapStat._insert_batch
            for i in range(0, len(new_stat_values), ins_batch):
                batch_values = new_stat_values[i:i + ins_batch]
                self.session.execute(stmt.values(batch_values))

        if queue.size() >= batch:
            self.task.apply_async(
                kwargs={'batch': batch},
                countdown=2,
                expires=10)

        return len(positions)
