from datetime import datetime
from datetime import timedelta

from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ichnaea.models import (
    CellMeasure,
    Measure,
    WifiMeasure,
    Stat,
)
from ichnaea.tasks import DatabaseTask
from ichnaea.worker import celery


def histogram_days(ago):
    today = datetime.utcnow().date()
    day = today - timedelta(days=ago)
    max_day = day + timedelta(days=1)
    return day, max_day


def histogram_query(session, model, max_day):
    query = session.query(func.count(model.id))
    query = query.filter(model.created < max_day)
    return query.first()[0]


def make_stat(name, time, value):
    stat = Stat(time=time, value=int(value))
    stat.name = name
    return stat


@celery.task(base=DatabaseTask)
def histogram(ago=1):
    day, max_day = histogram_days(ago)
    try:
        with histogram.db_session() as session:
            value = histogram_query(session, Measure, max_day)
            session.add(make_stat('location', day, value))
            session.commit()
            return 1
    except IntegrityError as exc:
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise histogram.retry(exc=exc)


@celery.task(base=DatabaseTask)
def cell_histogram(ago=1):
    day, max_day = histogram_days(ago)
    try:
        with cell_histogram.db_session() as session:
            value = histogram_query(session, CellMeasure, max_day)
            session.add(make_stat('cell', day, value))
            session.commit()
            return 1
    except IntegrityError as exc:
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise cell_histogram.retry(exc=exc)


@celery.task(base=DatabaseTask)
def wifi_histogram(ago=1):
    day, max_day = histogram_days(ago)
    try:
        with wifi_histogram.db_session() as session:
            value = histogram_query(session, WifiMeasure, max_day)
            session.add(make_stat('wifi', day, value))
            session.commit()
            return 1
    except IntegrityError as exc:
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise wifi_histogram.retry(exc=exc)


@celery.task(base=DatabaseTask)
def unique_cell_histogram(ago=1):
    day, max_day = histogram_days(ago)
    try:
        with unique_cell_histogram.db_session() as session:
            query = session.query(
                CellMeasure.radio, CellMeasure.mcc, CellMeasure.mnc,
                CellMeasure.lac, CellMeasure.cid).\
                group_by(CellMeasure.radio, CellMeasure.mcc, CellMeasure.mnc,
                         CellMeasure.lac, CellMeasure.cid)
            query = query.filter(CellMeasure.created < max_day)
            value = query.count()
            session.add(make_stat('unique_cell', day, value))
            session.commit()
            return 1
    except IntegrityError as exc:
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise unique_cell_histogram.retry(exc=exc)


@celery.task(base=DatabaseTask)
def unique_wifi_histogram(ago=1):
    day, max_day = histogram_days(ago)
    try:
        with unique_wifi_histogram.db_session() as session:
            query = session.query(func.count(distinct(WifiMeasure.key)))
            query = query.filter(WifiMeasure.created < max_day)
            value = query.first()[0]
            session.add(make_stat('unique_wifi', day, value))
            session.commit()
            return 1
    except IntegrityError as exc:
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise unique_wifi_histogram.retry(exc=exc)
