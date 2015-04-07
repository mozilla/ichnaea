from ichnaea.async.task import DatabaseTask
from ichnaea.customjson import kombu_loads
from ichnaea.data.area import (
    CellAreaUpdater,
    OCIDCellAreaUpdater,
)
from ichnaea.data.observation import (
    CellObservationQueue,
    WifiObservationQueue,
)
from ichnaea.data.report import ReportQueue
from ichnaea.data.station import (
    CellRemover,
    CellUpdater,
    WifiRemover,
    WifiUpdater,
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
def insert_measures_cell(self, entries, userid=None, utcnow=None):
    with self.db_session() as session:
        queue = CellObservationQueue(self, session, utcnow=utcnow)
        length = queue.insert(entries, userid=userid)
        session.commit()
    return length


@celery.task(base=DatabaseTask, bind=True, queue='celery_insert')
def insert_measures_wifi(self, entries, userid=None, utcnow=None):
    with self.db_session() as session:
        queue = WifiObservationQueue(self, session, utcnow=utcnow)
        length = queue.insert(entries, userid=userid)
        session.commit()
    return length


@celery.task(base=DatabaseTask, bind=True)
def location_update_cell(self, min_new=10, max_new=100, batch=10):
    with self.db_session() as session:
        updater = CellUpdater(
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
        updater = WifiUpdater(
            self, session,
            min_new=min_new,
            max_new=max_new,
            remove_task=remove_wifi)
        wifis, moving = updater.update(batch=batch)
        session.commit()
    return (wifis, moving)


@celery.task(base=DatabaseTask, bind=True)
def remove_cell(self, cell_keys):
    with self.db_session() as session:
        length = CellRemover(self, session).remove(cell_keys)
        session.commit()
    return length


@celery.task(base=DatabaseTask, bind=True)
def remove_wifi(self, wifi_keys):
    with self.db_session() as session:
        length = WifiRemover(self, session).remove(wifi_keys)
        session.commit()
    return length


@celery.task(base=DatabaseTask, bind=True)
def scan_areas(self, batch=100):
    updater = CellAreaUpdater(self, None)
    length = updater.scan(update_area, batch=batch)
    return length


@celery.task(base=DatabaseTask, bind=True)
def update_area(self, area_key, cell_type='cell'):
    with self.db_session() as session:
        if cell_type == 'ocid':
            updater = OCIDCellAreaUpdater(self, session)
        else:
            updater = CellAreaUpdater(self, session)
        updater.update(area_key)
        session.commit()
