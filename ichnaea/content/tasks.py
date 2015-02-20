from datetime import timedelta

from ichnaea.async.task import DatabaseTask
from ichnaea.models.content import (
    Stat,
    StatKey,
)
from ichnaea.models import (
    Cell,
    CellObservation,
    OCIDCell,
    Wifi,
    WifiObservation,
)
from ichnaea import util
from ichnaea.worker import celery


def daily_task_days(ago):
    today = util.utcnow().date()
    day = today - timedelta(days=ago)
    max_day = day + timedelta(days=1)
    return day, max_day


def add_stat(session, stat_key, day, value):
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
    if date is None:  # pragma: no cover
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
    return (session.query(model)
                   .filter(model.created < max_day)
                   .filter(model.created >= min_day)
                   .count())


def histogram_task(db_session, model, stat_key, ago=1):
    day, max_day = daily_task_days(ago)
    with db_session() as session:
        value = histogram_query(session, model, day, max_day)
        add_stat(session, stat_key, day, value)
        session.commit()
    return 1


@celery.task(base=DatabaseTask, bind=True)
def cell_histogram(self, ago=1):
    return histogram_task(
        self.db_session, CellObservation, StatKey.cell, ago=ago)


@celery.task(base=DatabaseTask, bind=True)
def wifi_histogram(self, ago=1):
    return histogram_task(
        self.db_session, WifiObservation, StatKey.wifi, ago=ago)


@celery.task(base=DatabaseTask, bind=True)
def unique_cell_histogram(self, ago=1):
    return histogram_task(
        self.db_session, Cell, StatKey.unique_cell, ago=ago)


@celery.task(base=DatabaseTask, bind=True)
def unique_ocid_cell_histogram(self, ago=1):
    return histogram_task(
        self.db_session, OCIDCell, StatKey.unique_ocid_cell, ago=ago)


@celery.task(base=DatabaseTask, bind=True)
def unique_wifi_histogram(self, ago=1):
    return histogram_task(
        self.db_session, Wifi, StatKey.unique_wifi, ago=ago)
