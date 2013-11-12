from celery.utils.log import get_task_logger
from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ichnaea.content.models import Stat
from ichnaea.models import (
    CellMeasure,
    Measure,
    WifiMeasure,
)
from ichnaea.tasks import (
    DatabaseTask,
    daily_task_days,
)
from ichnaea.worker import celery

logger = get_task_logger(__name__)


def histogram_query(session, model, max_day):
    query = session.query(func.count(model.id))
    query = query.filter(model.created < max_day)
    return query.first()[0]


def make_stat(name, time, value):
    stat = Stat(time=time, value=int(value))
    stat.name = name
    return stat


@celery.task(base=DatabaseTask, bind=True)
def histogram(self, ago=1):
    day, max_day = daily_task_days(ago)
    try:
        with self.db_session() as session:
            value = histogram_query(session, Measure, max_day)
            session.add(make_stat('location', day, value))
            session.commit()
            return 1
    except IntegrityError as exc:
        logger.exception('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def cell_histogram(self, ago=1):
    day, max_day = daily_task_days(ago)
    try:
        with self.db_session() as session:
            value = histogram_query(session, CellMeasure, max_day)
            session.add(make_stat('cell', day, value))
            session.commit()
            return 1
    except IntegrityError as exc:
        logger.exception('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def wifi_histogram(self, ago=1):
    day, max_day = daily_task_days(ago)
    try:
        with self.db_session() as session:
            value = histogram_query(session, WifiMeasure, max_day)
            session.add(make_stat('wifi', day, value))
            session.commit()
            return 1
    except IntegrityError as exc:
        logger.exception('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def unique_cell_histogram(self, ago=1):
    day, max_day = daily_task_days(ago)
    try:
        with self.db_session() as session:
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
        logger.exception('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def unique_wifi_histogram(self, ago=1):
    day, max_day = daily_task_days(ago)
    try:
        with self.db_session() as session:
            query = session.query(func.count(distinct(WifiMeasure.key)))
            query = query.filter(WifiMeasure.created < max_day)
            value = query.first()[0]
            session.add(make_stat('unique_wifi', day, value))
            session.commit()
            return 1
    except IntegrityError as exc:
        logger.exception('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)
