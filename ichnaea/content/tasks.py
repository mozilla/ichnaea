from datetime import timedelta

from ichnaea.async.task import DatabaseTask
from ichnaea.content.models import (
    Stat,
    STAT_TYPE,
)
from ichnaea.models import (
    Cell,
    CellMeasure,
    OCIDCell,
    Wifi,
    WifiMeasure,
    CELLID_LAC,
)
from ichnaea import util
from ichnaea.worker import celery


def daily_task_days(ago):
    today = util.utcnow().date()
    day = today - timedelta(days=ago)
    max_day = day + timedelta(days=1)
    return day, max_day


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


def histogram_query(session, model, min_day, max_day):
    query = session.query(model).filter(
        model.created < max_day).filter(
        model.created >= min_day)
    if isinstance(model, Cell):
        query = query.filter(model.lac != CELLID_LAC)
    return query.count()


def histogram_task(db_session, model, statname, ago=1):
    day, max_day = daily_task_days(ago)
    with db_session() as session:
        value = histogram_query(session, model, day, max_day)
        add_stat(session, statname, day, value)
        session.commit()
    return 1


@celery.task(base=DatabaseTask, bind=True)
def cell_histogram(self, ago=1):
    try:
        return histogram_task(self.db_session, CellMeasure, 'cell', ago=ago)
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def wifi_histogram(self, ago=1):
    try:
        return histogram_task(self.db_session, WifiMeasure, 'wifi', ago=ago)
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def unique_cell_histogram(self, ago=1):
    try:
        return histogram_task(self.db_session, Cell, 'unique_cell', ago=ago)
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def unique_ocid_cell_histogram(self, ago=1):
    try:
        return histogram_task(
            self.db_session, OCIDCell, 'unique_ocid_cell', ago=ago)
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def unique_wifi_histogram(self, ago=1):
    try:
        return histogram_task(self.db_session, Wifi, 'unique_wifi', ago=ago)
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)
