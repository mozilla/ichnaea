# BBB: Deprecated tasks, moved to ichnaea.data.tasks

from ichnaea.async.task import DatabaseTask
from ichnaea.data import tasks as data_tasks
from ichnaea.worker import celery


@celery.task(base=DatabaseTask, bind=True, queue='incoming')
def insert_measures(self, items=None, nickname=''):
    return data_tasks.insert_measures.delay(items=items, nickname=nickname)


@celery.task(base=DatabaseTask, bind=True, queue='insert')
def insert_cell_measures(self, entries, userid=None,
                         max_measures_per_cell=11000,
                         utcnow=None):
    return data_tasks.insert_measures_cell.delay(
        entries, userid=userid,
        max_measures_per_cell=max_measures_per_cell, utcnow=utcnow)


@celery.task(base=DatabaseTask, bind=True, queue='insert')
def insert_wifi_measures(self, entries, userid=None,
                         max_measures_per_wifi=11000,
                         utcnow=None):
    return data_tasks.insert_measures_wifi.delay(
        entries, userid=userid,
        max_measures_per_wifi=max_measures_per_wifi, utcnow=utcnow)
