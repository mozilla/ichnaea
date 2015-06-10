from ichnaea.async.app import celery_app
from ichnaea.async.task import BaseTask


@celery_app.task(base=BaseTask, bind=True)
def write_cellmeasure_s3_backups(self,
                                 limit=100,
                                 batch=10000,
                                 countdown=300,
                                 cleanup_zip=True):  # pragma: no cover
    # BBB
    pass


@celery_app.task(base=BaseTask, bind=True)
def write_wifimeasure_s3_backups(self,
                                 limit=100,
                                 batch=10000,
                                 countdown=300,
                                 cleanup_zip=True):  # pragma: no cover
    # BBB
    pass


@celery_app.task(base=BaseTask, bind=True)
def schedule_cellmeasure_archival(self, limit=100,
                                  batch=1000000):  # pragma: no cover
    # BBB
    pass


@celery_app.task(base=BaseTask, bind=True)
def schedule_wifimeasure_archival(self, limit=100,
                                  batch=1000000):  # pragma: no cover
    # BBB
    pass


@celery_app.task(base=BaseTask, bind=True)
def verified_delete(self, block_id, batch=10000):  # pragma: no cover
    # BBB
    pass


@celery_app.task(base=BaseTask, bind=True)
def delete_cellmeasure_records(self, limit=100, days_old=7, countdown=300,
                               batch=10000):  # pragma: no cover
    # BBB
    pass


@celery_app.task(base=BaseTask, bind=True)
def delete_wifimeasure_records(self, limit=100, days_old=7, countdown=300,
                               batch=10000):  # pragma: no cover
    # BBB
    pass
