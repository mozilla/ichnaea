from ichnaea.async.app import celery_app
from ichnaea.async.task import DatabaseTask
from ichnaea.customjson import kombu_loads
from ichnaea.data.area import (
    CellAreaUpdater,
    OCIDCellAreaUpdater,
)
from ichnaea.data.export import (
    GeosubmitUploader,
    ExportScheduler,
    ReportExporter,
    S3Uploader,
)
from ichnaea.data.mapstat import MapStatUpdater
from ichnaea.data.observation import (
    CellObservationQueue,
    WifiObservationQueue,
)
from ichnaea.data.report import (
    ReportQueueV1,
    ReportQueueV2,
)
from ichnaea.data.score import ScoreUpdater
from ichnaea.data.station import (
    CellRemover,
    CellUpdater,
    WifiRemover,
    WifiUpdater,
)
from ichnaea.data.stats import StatCounterUpdater
from ichnaea.models import ApiKey


@celery_app.task(base=DatabaseTask, bind=True, queue='celery_incoming')
def insert_measures(self, items=None, nickname='', email='',
                    api_key_text=None):
    if not items:  # pragma: no cover
        return 0

    reports = kombu_loads(items)
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            api_key = api_key_text and ApiKey.getkey(session, api_key_text)

            queue = ReportQueueV1(self, session, pipe,
                                  api_key,
                                  insert_cell_task=insert_measures_cell,
                                  insert_wifi_task=insert_measures_wifi)
            length = queue.insert(reports, nickname=nickname, email=email)
    return length


@celery_app.task(base=DatabaseTask, bind=True, queue='celery_insert')
def insert_measures_cell(self, entries, userid=None, utcnow=None):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            queue = CellObservationQueue(self, session, pipe, utcnow=utcnow)
            length = queue.insert(entries, userid=userid)
    return length


@celery_app.task(base=DatabaseTask, bind=True, queue='celery_insert')
def insert_measures_wifi(self, entries, userid=None, utcnow=None):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            queue = WifiObservationQueue(self, session, pipe, utcnow=utcnow)
            length = queue.insert(entries, userid=userid)
    return length


@celery_app.task(base=DatabaseTask, bind=True)
def location_update_cell(self, min_new=10, max_new=100, batch=10):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            updater = CellUpdater(
                self, session, pipe,
                min_new=min_new,
                max_new=max_new,
                remove_task=remove_cell)
            cells, moving = updater.update(batch=batch)
    return (cells, moving)


@celery_app.task(base=DatabaseTask, bind=True)
def location_update_wifi(self, min_new=10, max_new=100, batch=10):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            updater = WifiUpdater(
                self, session, pipe,
                min_new=min_new,
                max_new=max_new,
                remove_task=remove_wifi)
            wifis, moving = updater.update(batch=batch)
    return (wifis, moving)


@celery_app.task(base=DatabaseTask, bind=True, queue='celery_export')
def schedule_export_reports(self):
    scheduler = ExportScheduler(self, None)
    return scheduler.schedule(export_reports)


@celery_app.task(base=DatabaseTask, bind=True, queue='celery_export')
def export_reports(self, export_queue_name, queue_key=None):
    exporter = ReportExporter(self, None, export_queue_name, queue_key)
    return exporter.export(export_reports, upload_reports)


@celery_app.task(base=DatabaseTask, bind=True, queue='celery_reports')
def queue_reports(self, reports=(), api_key=None, email=None, nickname=None):
    with self.redis_pipeline() as pipe:
        queue = ReportQueueV2(self, None, pipe,
                              api_key=api_key,
                              email=email,
                              nickname=nickname)
        length = queue.insert(reports)
    return length


@celery_app.task(base=DatabaseTask, bind=True, queue='celery_upload')
def upload_reports(self, export_queue_name, data, queue_key=None):
    uploaders = {
        'http': GeosubmitUploader,
        'https': GeosubmitUploader,
        's3': S3Uploader,
    }
    export_queue = self.app.export_queues[export_queue_name]
    uploader_type = uploaders.get(export_queue.scheme, None)

    if uploader_type is not None:
        uploader = uploader_type(self, None, export_queue_name, queue_key)
        return uploader.upload(data)


@celery_app.task(base=DatabaseTask, bind=True)
def remove_cell(self, cell_keys):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            length = CellRemover(self, session, pipe).remove(cell_keys)
    return length


@celery_app.task(base=DatabaseTask, bind=True)
def remove_wifi(self, wifi_keys):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            length = WifiRemover(self, session, pipe).remove(wifi_keys)
    return length


@celery_app.task(base=DatabaseTask, bind=True)
def scan_areas(self, batch=100):
    updater = CellAreaUpdater(self, None)
    length = updater.scan(update_area, batch=batch)
    return length


@celery_app.task(base=DatabaseTask, bind=True)
def update_area(self, area_key, cell_type='cell'):
    with self.db_session() as session:
        if cell_type == 'ocid':
            updater = OCIDCellAreaUpdater(self, session)
        else:
            updater = CellAreaUpdater(self, session)
        updater.update(area_key)


@celery_app.task(base=DatabaseTask, bind=True)
def update_mapstat(self, batch=1000):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            updater = MapStatUpdater(self, session, pipe)
            updater.update(batch=batch)


@celery_app.task(base=DatabaseTask, bind=True)
def update_score(self, batch=1000):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            updater = ScoreUpdater(self, session, pipe)
            updater.update(batch=batch)


@celery_app.task(base=DatabaseTask, bind=True)
def update_statcounter(self, ago=1):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            updater = StatCounterUpdater(self, session, pipe)
            updater.update(ago=ago)
