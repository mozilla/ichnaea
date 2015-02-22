from ichnaea.customjson import (
    kombu_dumps,
    kombu_loads,
)
from ichnaea.geocalc import centroid, range_to_points
from ichnaea.models import (
    CELL_MODEL_KEYS,
    CellArea,
)
from ichnaea import util

UPDATE_KEY = {
    'cell': 'update_cell',
    'cell_lac': 'update_cell_lac',
    'wifi': 'update_wifi',
}


def enqueue_lacs(session, redis_client, lac_keys,
                 pipeline_key, expire=86400, batch=100):
    pipe = redis_client.pipeline()
    lac_json = [str(kombu_dumps(lac)) for lac in lac_keys]

    while lac_json:
        pipe.lpush(pipeline_key, *lac_json[:batch])
        lac_json = lac_json[batch:]

    # Expire key after 24 hours
    pipe.expire(pipeline_key, expire)
    pipe.execute()


def dequeue_lacs(redis_client, pipeline_key, batch=100):
    pipe = redis_client.pipeline()
    pipe.multi()
    pipe.lrange(pipeline_key, 0, batch - 1)
    pipe.ltrim(pipeline_key, batch, -1)
    return [kombu_loads(item) for item in pipe.execute()[0]]


class CellAreaUpdater(object):

    def __init__(self, task, session,
                 cell_model_key='cell',
                 cell_area_model_key='cell_area'):
        self.task = task
        self.session = session
        self.cell_model_key = cell_model_key
        self.cell_model = CELL_MODEL_KEYS[cell_model_key]
        self.cell_area_model_key = cell_area_model_key
        self.cell_area_model = CELL_MODEL_KEYS[cell_area_model_key]
        self.redis_client = task.app.redis_client
        self.stats_client = task.stats_client
        self.utcnow = util.utcnow()

    def scan(self, update_task, batch=100):
        redis_areas = dequeue_lacs(
            self.redis_client, UPDATE_KEY['cell_lac'], batch=batch)
        areas = set([CellArea.to_hashkey(area) for area in redis_areas])

        for area in areas:
            update_task.delay(
                area.radio,
                area.mcc,
                area.mnc,
                area.lac,
                cell_model_key=self.cell_model_key,
                cell_area_model_key=self.cell_area_model_key)
        return len(areas)

    def update(self, radio, mcc, mnc, lac):
        # Select all cells in this area and derive a bounding box for them
        cell_query = (self.session.query(self.cell_model)
                                  .filter(self.cell_model.radio == radio)
                                  .filter(self.cell_model.mcc == mcc)
                                  .filter(self.cell_model.mnc == mnc)
                                  .filter(self.cell_model.lac == lac)
                                  .filter(self.cell_model.lat.isnot(None))
                                  .filter(self.cell_model.lon.isnot(None)))

        cells = cell_query.all()

        area_query = (self.session.query(self.cell_area_model)
                                  .filter(self.cell_area_model.radio == radio)
                                  .filter(self.cell_area_model.mcc == mcc)
                                  .filter(self.cell_area_model.mnc == mnc)
                                  .filter(self.cell_area_model.lac == lac))

        if len(cells) == 0:
            # If there are no more underlying cells, delete the area entry
            area_query.delete()
        else:
            # Otherwise update the area entry based on all the cells
            area = area_query.first()

            points = [(c.lat, c.lon) for c in cells]
            min_lat = min([c.min_lat for c in cells])
            min_lon = min([c.min_lon for c in cells])
            max_lat = max([c.max_lat for c in cells])
            max_lon = max([c.max_lon for c in cells])

            bbox_points = [(min_lat, min_lon),
                           (min_lat, max_lon),
                           (max_lat, min_lon),
                           (max_lat, max_lon)]

            ctr = centroid(points)
            rng = range_to_points(ctr, bbox_points)

            # Switch units back to meters
            ctr_lat = ctr[0]
            ctr_lon = ctr[1]
            rng = int(round(rng * 1000.0))

            # Now create or update the area
            num_cells = len(cells)
            avg_cell_range = int(sum(
                [cell.range for cell in cells]) / float(num_cells))
            if area is None:
                area = self.cell_area_model(
                    created=self.utcnow,
                    modified=self.utcnow,
                    radio=radio,
                    mcc=mcc,
                    mnc=mnc,
                    lac=lac,
                    lat=ctr_lat,
                    lon=ctr_lon,
                    range=rng,
                    avg_cell_range=avg_cell_range,
                    num_cells=num_cells,
                )
                self.session.add(area)
            else:
                area.modified = self.utcnow
                area.lat = ctr_lat
                area.lon = ctr_lon
                area.range = rng
                area.avg_cell_range = avg_cell_range
                area.num_cells = num_cells
