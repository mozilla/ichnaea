# BBB: Deprecated tasks, moved to ichnaea.data.tasks

from ichnaea.async.task import DatabaseTask
from ichnaea.data import tasks as data_tasks
from ichnaea.worker import celery


@celery.task(base=DatabaseTask, bind=True)
def remove_wifi(self, wifi_keys):
    return data_tasks.remove_wifi.delay(wifi_keys)


@celery.task(base=DatabaseTask, bind=True)
def remove_cell(self, cell_keys):
    return data_tasks.remove_cell.delay(cell_keys)


@celery.task(base=DatabaseTask, bind=True)
def backfill_cell_location_update(self, new_cell_measures):
    return data_tasks.backfill_cell_location_update.delay(new_cell_measures)


@celery.task(base=DatabaseTask, bind=True)
def cell_location_update(self, min_new=10, max_new=100, batch=10):
    return data_tasks.cell_location_update.delay(
        min_new=min_new, max_new=max_new, batch=batch)


@celery.task(base=DatabaseTask, bind=True)
def wifi_location_update(self, min_new=10, max_new=100, batch=10):
    return data_tasks.wifi_location_update.delay(
        min_new=min_new, max_new=max_new, batch=batch)


@celery.task(base=DatabaseTask, bind=True)
def scan_lacs(self, batch=100):
    return data_tasks.scan_lacs.delay(batch=batch)


@celery.task(base=DatabaseTask, bind=True)
def update_lac(self, radio, mcc, mnc, lac):
    return data_tasks.update_lac.delay(radio, mcc, mnc, lac)
