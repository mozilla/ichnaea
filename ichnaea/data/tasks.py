from ichnaea.async.app import celery_app
from ichnaea.async.task import BaseTask
from ichnaea.data.area import (
    CellAreaUpdater,
    OCIDCellAreaUpdater,
)
from ichnaea.data.export import (
    GeosubmitUploader,
    ExportQueue,
    ExportScheduler,
    ReportExporter,
    S3Uploader,
)
from ichnaea.data.internal import InternalUploader
from ichnaea.data.mapstat import MapStatUpdater
from ichnaea.data import monitor
from ichnaea.data import ocid
from ichnaea.data.report import ReportQueue
from ichnaea.data.score import ScoreUpdater
from ichnaea.data.station import (
    CellRemover,
    CellUpdater,
    WifiRemover,
    WifiUpdater,
)
from ichnaea.data.stats import StatCounterUpdater
from ichnaea.models import ApiKey


@celery_app.task(base=BaseTask, bind=True, queue='celery_ocid')
def export_modified_cells(self, hourly=True, _bucket=None):
    ocid.export_modified_cells(self, hourly=hourly, _bucket=_bucket)


@celery_app.task(base=BaseTask, bind=True, queue='celery_ocid')
def import_latest_ocid_cells(self, diff=True):
    ocid.import_latest_ocid_cells(
        self, diff=diff, update_area_task=update_area)


@celery_app.task(base=BaseTask, bind=True, queue='celery_ocid')
def import_ocid_cells(self, filename=None):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            ocid.import_ocid_cells(
                session, pipe, filename=filename, update_area_task=update_area)


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor')
def monitor_api_key_limits(self):
    return monitor.monitor_api_key_limits(self)


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor')
def monitor_api_users(self):
    return monitor.monitor_api_users(self)


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor')
def monitor_ocid_import(self):
    return monitor.monitor_ocid_import(self)


@celery_app.task(base=BaseTask, bind=True, queue='celery_monitor')
def monitor_queue_length(self):
    return monitor.monitor_queue_length(self)


@celery_app.task(base=BaseTask, bind=True, queue='celery_export')
def schedule_export_reports(self):
    scheduler = ExportScheduler(self, None)
    return scheduler.schedule(export_reports)


@celery_app.task(base=BaseTask, bind=True, queue='celery_export')
def export_reports(self, export_queue_name, queue_key=None):
    exporter = ReportExporter(self, None, export_queue_name, queue_key)
    return exporter.export(export_reports, upload_reports)


@celery_app.task(base=BaseTask, bind=True, queue='celery_incoming')
def insert_reports(self, reports=(),
                   api_key=None, email=None, ip=None, nickname=None):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            api_key = api_key and ApiKey.getkey(
                session, {'valid_key': api_key})

            queue = ReportQueue(self, session, pipe,
                                api_key=api_key,
                                email=email,
                                ip=ip,
                                nickname=nickname)
            length = queue.insert(reports)
    return length


@celery_app.task(base=BaseTask, bind=True, queue='celery_reports')
def queue_reports(self, reports=(),
                  api_key=None, email=None, ip=None, nickname=None):
    with self.redis_pipeline() as pipe:
        queue = ExportQueue(self, None, pipe,
                            api_key=api_key,
                            email=email,
                            ip=ip,
                            nickname=nickname)
        length = queue.insert(reports)
    return length


@celery_app.task(base=BaseTask, bind=True, queue='celery_upload')
def upload_reports(self, export_queue_name, data, queue_key=None):
    uploaders = {
        'http': GeosubmitUploader,
        'https': GeosubmitUploader,
        'internal': InternalUploader,
        's3': S3Uploader,
    }
    export_queue = self.app.export_queues[export_queue_name]
    uploader_type = uploaders.get(export_queue.scheme, None)

    if uploader_type is not None:
        uploader = uploader_type(self, None, export_queue_name, queue_key)
        return uploader.upload(data)


@celery_app.task(base=BaseTask, bind=True, queue='celery_cell')
def remove_cell(self, cell_keys):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            length = CellRemover(self, session, pipe).remove(cell_keys)
    return length


@celery_app.task(base=BaseTask, bind=True, queue='celery_wifi')
def remove_wifi(self, wifi_keys):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            length = WifiRemover(self, session, pipe).remove(wifi_keys)
    return length


@celery_app.task(base=BaseTask, bind=True, queue='celery_cell')
def update_cell(self, batch=1000):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            updater = CellUpdater(
                self, session, pipe,
                remove_task=remove_cell,
                update_task=update_cell)
            cells, moving = updater.update(batch=batch)
    return (cells, moving)


@celery_app.task(base=BaseTask, bind=True, queue='celery_wifi')
def update_wifi(self, batch=1000):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            updater = WifiUpdater(
                self, session, pipe,
                remove_task=remove_wifi,
                update_task=update_wifi)
            updater.update(batch=batch)


@celery_app.task(base=BaseTask, bind=True, queue='celery_cell')
def scan_areas(self, batch=100):
    updater = CellAreaUpdater(self, None)
    length = updater.scan(update_area, batch=batch)
    return length


@celery_app.task(base=BaseTask, bind=True)
def update_area(self, area_keys, cell_type='cell', queue='celery_cell'):
    with self.db_session() as session:
        if cell_type == 'ocid':
            updater = OCIDCellAreaUpdater(self, session)
        else:
            updater = CellAreaUpdater(self, session)
        updater.update(area_keys)


@celery_app.task(base=BaseTask, bind=True)
def update_mapstat(self, batch=1000):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            updater = MapStatUpdater(self, session, pipe)
            updater.update(batch=batch)


@celery_app.task(base=BaseTask, bind=True)
def update_score(self, batch=1000):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            updater = ScoreUpdater(self, session, pipe)
            updater.update(batch=batch)


@celery_app.task(base=BaseTask, bind=True)
def update_statcounter(self, ago=1):
    with self.redis_pipeline() as pipe:
        with self.db_session() as session:
            updater = StatCounterUpdater(self, session, pipe)
            updater.update(ago=ago)
