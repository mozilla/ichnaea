from celery import Task

from ichnaea.db import Measure
from ichnaea.db import db_worker_session
from ichnaea.worker import celery


class DatabaseTask(Task):
    abstract = True

    @classmethod
    def on_bound(cls, app):
        super(DatabaseTask, cls).on_bound(app)
        cls.db_master = app.db_master

    def db_session(self):
        # returns a context manager
        return db_worker_session(self.db_master)


@celery.task(base=DatabaseTask, acks_late=False, ignore_result=True)
def add_measure(lat=0, lon=0):
    with add_measure.db_session() as session:
        measure = Measure(lat=lat, lon=lon)
        session.add(measure)
        session.commit()
