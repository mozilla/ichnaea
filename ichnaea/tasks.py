from operator import itemgetter

from celery import Task
from sqlalchemy.sql.expression import text

from ichnaea.db import (
    db_worker_session,
    Stat,
)
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
def histogram():
    query = text("select date(time) as day, count(*) as num from measure "
                 "where date_sub(curdate(), interval 30 day) <= time and "
                 "date(time) <= curdate() group by date(time)")
    try:
        with histogram.db_session() as session:
            rows = session.execute(query).fetchall()
            stats = []
            for row in sorted(rows, key=itemgetter(0)):
                stat = Stat(time=row[0], value=row[1])
                stat.name = 'location'
                stats.append(stat)
            session.add_all(stats)
            session.commit()
    except Exception as exc:
        raise histogram.retry(exc=exc)
