from ichnaea.async.task import DatabaseTask
from ichnaea.customjson import kombu_loads
from ichnaea.data.area import (
    enqueue_lacs,
    CellAreaUpdater,
    UPDATE_KEY,
)
from ichnaea.data.observation import (
    CellObservationQueue,
    WifiObservationQueue,
)
from ichnaea.data.report import ReportQueue
from ichnaea.data.station import (
    CellStationUpdater,
    WifiStationUpdater,
)
from ichnaea.models import (
    Cell,
    CellArea,
    Wifi,
)
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
    updater = CellAreaUpdater(
        self, None,
        cell_model_key='cell',
        cell_area_model_key='cell_area')
    length = updater.scan(update_lac, batch=batch)
    return length


@celery.task(base=DatabaseTask, bind=True)
def update_lac(self, radio, mcc, mnc, lac,
               cell_model_key='cell',
               cell_area_model_key='cell_area'):
    with self.db_session() as session:
        updater = CellAreaUpdater(
            self, session,
            cell_model_key=cell_model_key,
            cell_area_model_key=cell_area_model_key)
        updater.update(radio, mcc, mnc, lac)
        session.commit()
