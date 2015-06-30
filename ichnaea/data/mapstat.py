from sqlalchemy.orm import load_only

from ichnaea.data.base import DataTask
from ichnaea.models.content import (
    MapStat,
)
from ichnaea import util


class MapStatUpdater(DataTask):

    def __init__(self, task, session, pipe):
        DataTask.__init__(self, task, session)
        self.pipe = pipe

    def update(self, batch=1000):
        queue = self.task.app.data_queues['update_mapstat']
        today = util.utcnow().date()
        positions = queue.dequeue(batch=batch)
        if not positions:
            return 0

        found = set()
        wanted = set()
        for position in positions:
            wanted.add(MapStat.to_hashkey(lat=MapStat.scale(position['lat']),
                                          lon=MapStat.scale(position['lon'])))

        stat_iter = MapStat.iterkeys(
            self.session, list(wanted),
            extra=lambda query: query.options(load_only('lat', 'lon')))

        found = set([stat.hashkey() for stat in stat_iter])

        for key in (wanted - found):
            stmt = MapStat.__table__.insert(
                on_duplicate='id = id').values(
                time=today, lat=key.lat, lon=key.lon)
            self.session.execute(stmt)

        if queue.size() >= batch:
            self.task.apply_async(
                kwargs={'batch': batch},
                countdown=2,
                expires=10)

        return len(positions)
