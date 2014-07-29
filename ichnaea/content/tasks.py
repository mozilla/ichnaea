from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ichnaea.async.task import DatabaseTask
from ichnaea.content.models import (
    Stat,
    STAT_TYPE,
)
from ichnaea.models import (
    Cell,
    CellMeasure,
    Wifi,
    WifiMeasure,
    CELLID_LAC,
)
from ichnaea.tasks import daily_task_days
from ichnaea import util
from ichnaea.worker import celery


def histogram_query(session, model, min_day, max_day):
    query = session.query(
        func.count(model.id)).filter(
        model.created < max_day).filter(
        model.created >= min_day)
    if isinstance(model, Cell):
        query = query.filter(model.lac != CELLID_LAC)
    return query.first()[0]


def add_stat(session, name, day, value):
    stat_key = STAT_TYPE[name]
    todays_stat = get_stat(session, stat_key, exact=True, date=day)
    if todays_stat:
        return

    yesterday = day - timedelta(days=1)
    before = get_stat(session, stat_key, exact=False, date=yesterday)
    old_value = 0
    if before is not None:
        old_value = int(before.value)

    stat = Stat(key=stat_key, time=day, value=old_value + int(value))
    session.add(stat)


def get_stat(session, stat_key, exact=True, date=None):
    if date is None:
        date = util.utcnow().date()
    query = session.query(Stat).filter(
        Stat.key == stat_key)
    if exact:
        query = query.filter(Stat.time == date)
    else:
        query = query.filter(
            Stat.time <= date).order_by(
            Stat.time.desc())

    return query.first()


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
