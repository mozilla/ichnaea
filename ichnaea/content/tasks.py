from datetime import timedelta, datetime

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ichnaea.content.models import (
    Stat,
    STAT_TYPE,
)
from ichnaea.models import (
    Cell,
    CellMeasure,
    Wifi,
    WifiMeasure,
)
from ichnaea.tasks import (
    DatabaseTask,
    daily_task_days,
)
from ichnaea.worker import celery


def histogram_query(session, model, min_day, max_day):
    query = session.query(
        func.count(model.id)).filter(
        model.created < max_day).filter(
        model.created >= min_day)
    return query.first()[0]


def add_stat(session, name, day, value):
    stat_key = STAT_TYPE[name]
    query = session.query(Stat.value).filter(
        Stat.key == stat_key).filter(
        Stat.time == day - timedelta(days=1))
    result = query.first()
    before = 0
    if result is not None:
        before = int(result[0])

    # on duplicate key, do a no-op change
    stmt = Stat.__table__.insert(
        on_duplicate='time=time').values(
        key=stat_key, time=day, value=before + int(value))
    session.execute(stmt)

def incr_stat(session, name, incr, date=datetime.utcnow().date()):
    stat_key = STAT_TYPE[name]
    result = get_curr_stat(session, name)
    cumulative = incr
    if result is not None:
        cumulative += result

    # on duplicate key, update existing
    stmt = Stat.__table__.insert(
        on_duplicate='value=%s' % cumulative).values(
            key=stat_key, time=date, value=cumulative)
    session.execute(stmt)

def get_curr_stat(session, name, date=datetime.utcnow().date()):
    stat_key = STAT_TYPE[name]
    query = session.query(Stat.value).filter(
        Stat.key == stat_key).filter(
        Stat.time <= date).order_by(
        Stat.time.desc())
    result = query.first()
    if result is not None:
        return int(result[0])
    else:
        return None

@celery.task(base=DatabaseTask, bind=True)
def cell_histogram(self, ago=1):
    day, max_day = daily_task_days(ago)
    try:
        with self.db_session() as session:
            value = histogram_query(session, CellMeasure, day, max_day)
            add_stat(session, 'cell', day, value)
            session.commit()
            return 1
    except IntegrityError as exc:
        self.heka_client.raven('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def wifi_histogram(self, ago=1):
    day, max_day = daily_task_days(ago)
    try:
        with self.db_session() as session:
            value = histogram_query(session, WifiMeasure, day, max_day)
            add_stat(session, 'wifi', day, value)
            session.commit()
            return 1
    except IntegrityError as exc:
        self.heka_client.raven('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def unique_cell_histogram(self, ago=1):
    day, max_day = daily_task_days(ago)
    try:
        with self.db_session() as session:
            value = histogram_query(session, Cell, day, max_day)
            add_stat(session, 'unique_cell', day, value)
            session.commit()
            return 1
    except IntegrityError as exc:
        self.heka_client.raven('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def unique_wifi_histogram(self, ago=1):
    day, max_day = daily_task_days(ago)
    try:
        with self.db_session() as session:
            value = histogram_query(session, Wifi, day, max_day)
            add_stat(session, 'unique_wifi', day, value)
            session.commit()
            return 1
    except IntegrityError as exc:
        self.heka_client.raven('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)
