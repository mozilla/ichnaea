from sqlalchemy.sql import and_, or_

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
        positions = queue.dequeue(batch=batch)

        # Scale from floating point degrees to integer counts of thousandths of
        # a degree; 1/1000 degree is about 110m at the equator.
        factor = 1000
        today = util.utcnow().date()
        tiles = {}
        # aggregate to tiles, according to factor
        for position in positions:
            tiles[(int(position['lat'] * factor),
                   int(position['lon'] * factor))] = True
        query = self.session.query(MapStat.lat, MapStat.lon)
        # dynamically construct a (lat, lon) in (list of tuples) filter
        # as MySQL isn't able to use indexes on such in queries
        lat_lon = []
        for (lat, lon) in tiles.keys():
            lat_lon.append(and_((MapStat.lat == lat), (MapStat.lon == lon)))
        query = query.filter(or_(*lat_lon))
        result = query.all()
        prior = {}
        for r in result:
            prior[(r.lat, r.lon)] = True
        for (lat, lon) in tiles.keys():
            old = prior.get((lat, lon), False)
            if not old:
                stmt = MapStat.__table__.insert(
                    on_duplicate='id = id').values(
                    time=today, lat=lat, lon=lon)
                self.session.execute(stmt)

        if queue.size() >= batch:
            self.task.apply_async(
                kwargs={'batch': batch},
                countdown=2,
                expires=10)

        return len(positions)
