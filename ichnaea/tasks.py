from celery import Task

from ichnaea.db import Measure
from ichnaea.db import db_worker_session
from ichnaea.worker import celery


class DatabaseTask(Task):
    abstract = True
    acks_late = True
    ignore_result = False
    max_retries = 3

    def db_session(self):
        # returns a context manager
        return db_worker_session(self.app.db_master)


@celery.task(base=DatabaseTask)
def add_measure(lat=0, lon=0, fail_counter=None):
    try:
        if fail_counter:
            fail_counter[0] += 1
        with add_measure.db_session() as session:
            measure = Measure(lat=lat, lon=lon)
            session.add(measure)
            if fail_counter:
                session.flush()
                measure2 = Measure(lat=0, lon=0)
                # provoke error via duplicate id
                measure2.id = measure.id
                session.add(measure2)
            session.commit()
    except Exception as exc:
        raise add_measure.retry(exc=exc)
