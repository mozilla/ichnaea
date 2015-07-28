from ichnaea.async.app import celery_app
from ichnaea.async.task import BaseTask
from ichnaea.data import tasks


@celery_app.task(base=BaseTask, bind=True)
def export_modified_cells(self, hourly=True, bucket=None):  # pragma: no cover
    # BBB
    tasks.export_modified_cells.delay(hourly=hourly)


@celery_app.task(base=BaseTask, bind=True)
def import_ocid_cells(self, filename=None, session=None):  # pragma: no cover
    # BBB
    tasks.import_ocid_cells()


@celery_app.task(base=BaseTask, bind=True)
def import_latest_ocid_cells(self, diff=True, filename=None,
                             session=None):  # pragma: no cover
    # BBB
    tasks.import_latest_ocid_cells(diff=diff)
