from operator import itemgetter

from celery import Task
from sqlalchemy.exc import IntegrityError
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
def histogram(start=30, end=0):
    query = text("select date(created) as day, count(*) as num "
                 "from measure where "
                 "date(created) >= date_sub(curdate(), interval %s day) and "
                 "date(created) <= date_sub(curdate(), interval %s day) "
                 "group by date(created)" % (int(start), int(end)))
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
            return len(stats)
    except IntegrityError as exc:
        # TODO log error
        return 0
    except Exception as exc:
        raise histogram.retry(exc=exc)
