from ichnaea.async.task import DatabaseTask
from ichnaea.customjson import kombu_loads
from ichnaea.data.observation import (
    CellObservationQueue,
    WifiObservationQueue,
)
from ichnaea.data.report import ReportQueue
from ichnaea.data.station import (
    enqueue_lacs,
    dequeue_lacs,
    CellStationUpdater,
    WifiStationUpdater,
    UPDATE_KEY,
)
from ichnaea.geocalc import centroid, range_to_points
from ichnaea.models import (
    Cell,
    CELL_MODEL_KEYS,
    CellArea,
    Wifi,
)
from ichnaea import util
from ichnaea.worker import celery


@celery.task(base=DatabaseTask, bind=True, queue='celery_incoming')
def insert_measures(self, items=None, nickname='', email='',
                    api_key_log=False, api_key_name=None):
    if not items:  # pragma: no cover
        return 0

    reports = kombu_loads(items)
    with self.db_session() as session:
        queue = ReportQueue(self, session,
                            api_key_log=api_key_log,
                            api_key_name=api_key_name,
                            insert_cell_task=insert_measures_cell,
                            insert_wifi_task=insert_measures_wifi)
        length = queue.insert(reports, nickname=nickname, email=email)
        session.commit()
    return length


@celery.task(base=DatabaseTask, bind=True, queue='celery_insert')
def insert_measures_cell(self, entries, userid=None,
                         max_observations_per_cell=11000,
                         utcnow=None):

    with self.db_session() as session:
        queue = CellObservationQueue(
            self, session, utcnow=utcnow,
            max_observations=max_observations_per_cell)
        length = queue.insert(entries, userid=userid)
        session.commit()
    return length


@celery.task(base=DatabaseTask, bind=True, queue='celery_insert')
def insert_measures_wifi(self, entries, userid=None,
                         max_observations_per_wifi=11000,
                         utcnow=None):

    with self.db_session() as session:
        queue = WifiObservationQueue(
            self, session, utcnow=utcnow,
            max_observations=max_observations_per_wifi)
        length = queue.insert(entries, userid=userid)
        session.commit()
    return length


@celery.task(base=DatabaseTask, bind=True)
def location_update_cell(self, min_new=10, max_new=100, batch=10):
    with self.db_session() as session:
        updater = CellStationUpdater(
            self, session,
            min_new=min_new,
            max_new=max_new,
            remove_task=remove_cell)
        cells, moving = updater.update(batch=batch)
        session.commit()
    return (cells, moving)


@celery.task(base=DatabaseTask, bind=True)
def location_update_wifi(self, min_new=10, max_new=100, batch=10):
    with self.db_session() as session:
        updater = WifiStationUpdater(
            self, session,
            min_new=min_new,
            max_new=max_new,
            remove_task=remove_wifi)
        wifis, moving = updater.update(batch=batch)
        session.commit()
    return (wifis, moving)


@celery.task(base=DatabaseTask, bind=True)
def remove_cell(self, cell_keys):
    cells_removed = 0
    redis_client = self.app.redis_client
    with self.db_session() as session:
        changed_lacs = set()

        for key in cell_keys:
            query = Cell.querykey(session, key)
            cells_removed += query.delete()
            changed_lacs.add(CellArea.to_hashkey(key))

        if changed_lacs:
            session.on_post_commit(
                enqueue_lacs,
                redis_client,
                changed_lacs,
                UPDATE_KEY['cell_lac'])

        session.commit()
    return cells_removed


@celery.task(base=DatabaseTask, bind=True)
def remove_wifi(self, wifi_keys):
    # BBB this might still get namedtuples encoded as a dicts for
    # one release, afterwards it'll get wifi hashkeys
    keys = [Wifi.to_hashkey(key=wifi['key']) for wifi in wifi_keys]
    with self.db_session() as session:
        query = Wifi.querykeys(session, keys)
        wifis = query.delete(synchronize_session=False)
        session.commit()
    return wifis


@celery.task(base=DatabaseTask, bind=True)
def scan_lacs(self, batch=100):
    """
    Find cell LACs that have changed and update the bounding box.
    This includes adding new LAC entries and removing them.
    """
    redis_client = self.app.redis_client
    redis_lacs = dequeue_lacs(
        redis_client, UPDATE_KEY['cell_lac'], batch=batch)
    lacs = set([CellArea.to_hashkey(lac) for lac in redis_lacs])

    for lac in lacs:
        update_lac.delay(
            lac.radio,
            lac.mcc,
            lac.mnc,
            lac.lac,
            cell_model_key='cell',
            cell_area_model_key='cell_area')
    return len(lacs)


@celery.task(base=DatabaseTask, bind=True)
def update_lac(self, radio, mcc, mnc, lac,
               cell_model_key='cell', cell_area_model_key='cell_area'):
    utcnow = util.utcnow()
    with self.db_session() as session:
        # Select all the cells in this LAC that aren't the virtual
        # cell itself, and derive a bounding box for them.

        cell_model = CELL_MODEL_KEYS[cell_model_key]
        cell_query = (session.query(cell_model)
                             .filter(cell_model.radio == radio)
                             .filter(cell_model.mcc == mcc)
                             .filter(cell_model.mnc == mnc)
                             .filter(cell_model.lac == lac)
                             .filter(cell_model.lat.isnot(None))
                             .filter(cell_model.lon.isnot(None)))

        cells = cell_query.all()

        cell_area_model = CELL_MODEL_KEYS[cell_area_model_key]
        lac_query = (session.query(cell_area_model)
                            .filter(cell_area_model.radio == radio)
                            .filter(cell_area_model.mcc == mcc)
                            .filter(cell_area_model.mnc == mnc)
                            .filter(cell_area_model.lac == lac))

        if len(cells) == 0:
            # If there are no more underlying cells, delete the lac entry
            lac_query.delete()
        else:
            # Otherwise update the lac entry based on all the cells
            lac_obj = lac_query.first()

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

            # Switch units back to DB preferred centimicrodegres angle
            # and meters distance.
            ctr_lat = ctr[0]
            ctr_lon = ctr[1]
            rng = int(round(rng * 1000.0))

            # Now create or update the LAC virtual cell
            num_cells = len(cells)
            avg_cell_range = int(sum(
                [cell.range for cell in cells])/float(num_cells))
            if lac_obj is None:
                lac_obj = cell_area_model(
                    created=utcnow,
                    modified=utcnow,
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
                session.add(lac_obj)
            else:
                lac_obj.modified = utcnow
                lac_obj.lat = ctr_lat
                lac_obj.lon = ctr_lon
                lac_obj.range = rng
                lac_obj.avg_cell_range = avg_cell_range
                lac_obj.num_cells = num_cells

        session.commit()
