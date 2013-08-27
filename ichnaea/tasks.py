from datetime import datetime
from datetime import timedelta

from celery import Task
from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ichnaea.db import (
    CellMeasure,
    db_worker_session,
    Measure,
    WifiMeasure,
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
def histogram(ago=1):
    today = datetime.utcnow().date()
    day = today - timedelta(days=ago)
    day_plus_one = day + timedelta(days=1)
    try:
        with histogram.db_session() as session:
            query = session.query(func.count(Measure.id))
            query = query.filter(Measure.created < day_plus_one)
            value = query.first()[0]
            stat = Stat(time=day, value=int(value))
            stat.name = 'location'
            session.add(stat)
            session.commit()
            return 1
    except IntegrityError as exc:
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise histogram.retry(exc=exc)


@celery.task(base=DatabaseTask)
def cell_histogram(ago=1):
    today = datetime.utcnow().date()
    day = today - timedelta(days=ago)
    day_plus_one = day + timedelta(days=1)
    try:
        with cell_histogram.db_session() as session:
            query = session.query(func.count(CellMeasure.id))
            query = query.filter(CellMeasure.created < day_plus_one)
            value = query.first()[0]
            stat = Stat(time=day, value=int(value))
            stat.name = 'cell'
            session.add(stat)
            session.commit()
            return 1
    except IntegrityError as exc:
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise cell_histogram.retry(exc=exc)


@celery.task(base=DatabaseTask)
def wifi_histogram(ago=1):
    today = datetime.utcnow().date()
    day = today - timedelta(days=ago)
    day_plus_one = day + timedelta(days=1)
    try:
        with wifi_histogram.db_session() as session:
            query = session.query(func.count(WifiMeasure.id))
            query = query.filter(WifiMeasure.created < day_plus_one)
            value = query.first()[0]
            stat = Stat(time=day, value=int(value))
            stat.name = 'wifi'
            session.add(stat)
            session.commit()
            return 1
    except IntegrityError as exc:
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise wifi_histogram.retry(exc=exc)


@celery.task(base=DatabaseTask)
def unique_cell_histogram(ago=1):
    today = datetime.utcnow().date()
    day = today - timedelta(days=ago)
    day_plus_one = day + timedelta(days=1)
    try:
        with unique_cell_histogram.db_session() as session:
            query = session.query(
                CellMeasure.radio, CellMeasure.mcc, CellMeasure.mnc,
                CellMeasure.lac, CellMeasure.cid).\
                group_by(CellMeasure.radio, CellMeasure.mcc, CellMeasure.mnc,
                         CellMeasure.lac, CellMeasure.cid)
            query = query.filter(CellMeasure.created < day_plus_one)
            value = query.count()
            stat = Stat(time=day, value=int(value))
            stat.name = 'unique_cell'
            session.add(stat)
            session.commit()
            return 1
    except IntegrityError as exc:
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise unique_cell_histogram.retry(exc=exc)


@celery.task(base=DatabaseTask)
def unique_wifi_histogram(ago=1):
    today = datetime.utcnow().date()
    day = today - timedelta(days=ago)
    day_plus_one = day + timedelta(days=1)
    try:
        with unique_wifi_histogram.db_session() as session:
            query = session.query(func.count(distinct(WifiMeasure.key)))
            query = query.filter(WifiMeasure.created < day_plus_one)
            value = query.first()[0]
            stat = Stat(time=day, value=int(value))
            stat.name = 'unique_wifi'
            session.add(stat)
            session.commit()
            return 1
    except IntegrityError as exc:
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise unique_wifi_histogram.retry(exc=exc)
