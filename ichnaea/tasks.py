from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from operator import attrgetter

from celery import Task
from celery.utils.log import get_task_logger
from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ichnaea.db import db_worker_session
from ichnaea.models import (
    Cell,
    CellMeasure,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
)
from ichnaea.worker import celery

logger = get_task_logger(__name__)


class DatabaseTask(Task):
    abstract = True
    acks_late = True
    ignore_result = True
    max_retries = 3

    def db_session(self):
        # returns a context manager
        return db_worker_session(self.app.db_master)


def daily_task_days(ago):
    today = datetime.utcnow().date()
    day = today - timedelta(days=ago)
    max_day = day + timedelta(days=1)
    return day, max_day


@celery.task(base=DatabaseTask, bind=True)  # pragma: no cover
def cleanup_kombu_message_table(self, ago=0):
    now = datetime.utcnow()
    now = now.replace(second=0, microsecond=0)
    now -= timedelta(days=ago)
    # by default retain the last 15 minutes of processed tasks
    now -= timedelta(minutes=15)
    stmt = text(
        'delete from kombu_message where visible = 0 and '
        'timestamp < "%s" limit 50000;' % now.isoformat()
    )
    with self.db_session() as session:
        session.execute(stmt)
        session.commit()


@celery.task(base=DatabaseTask, bind=True)
def schedule_new_moving_wifi_analysis(self, ago=1, batch=1000):
    day, max_day = daily_task_days(ago)
    try:
        with self.db_session() as session:
            query = session.query(
                func.count(distinct(WifiMeasure.key))).filter(
                WifiMeasure.created < max_day).filter(
                WifiMeasure.created >= day)
            result = query.first()[0]
            if result == 0:
                return 0
            offset = 0
            batches = []
            while offset < result:
                batches.append(offset)
                blacklist_moving_wifis.delay(
                    ago=ago, offset=offset, batch=batch)
                offset += batch
            return len(batches)
    except IntegrityError as exc:  # pragma: no cover
        logger.exception('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def blacklist_moving_wifis(self, ago=1, offset=0, batch=1000):
    # TODO: this doesn't take into account wifi AP's which have
    # permanently moved after a certain date

    # maximum difference of two decimal places, ~5km at equator
    # or ~2km at 67 degrees north
    max_difference = 500000
    day, max_day = daily_task_days(ago)
    # only look at the past 30 days for movement
    max_past_days = day - timedelta(days=30)
    try:
        with self.db_session() as session:
            query = session.query(distinct(WifiMeasure.key)).filter(
                WifiMeasure.created < max_day).filter(
                WifiMeasure.created >= day).order_by(
                WifiMeasure.id).limit(batch).offset(offset)
            new_wifis = [w[0] for w in query.all()]
            if not new_wifis:  # pragma: no cover
                # nothing to be done
                return []
            # check min/max lat/lon
            query = session.query(
                WifiMeasure.key, func.max(WifiMeasure.lat),
                func.min(WifiMeasure.lat), func.max(WifiMeasure.lon),
                func.min(WifiMeasure.lon)).filter(
                WifiMeasure.key.in_(new_wifis)).filter(
                WifiMeasure.created > max_past_days).group_by(WifiMeasure.key)
            results = query.all()
            moving_keys = set()
            for result in results:
                wifi_key, max_lat, min_lat, max_lon, min_lon = result
                diff_lat = abs(max_lat - min_lat)
                diff_lon = abs(max_lon - min_lon)
                if diff_lat >= max_difference or diff_lon >= max_difference:
                    moving_keys.add(wifi_key)
            if moving_keys:
                utcnow = datetime.utcnow()
                query = session.query(WifiBlacklist.key).filter(
                    WifiBlacklist.key.in_(moving_keys))
                already_blocked = set([a[0] for a in query.all()])
                moving_keys = moving_keys - already_blocked
                if not moving_keys:
                    return []
                for key in moving_keys:
                    # TODO: on duplicate key ignore
                    session.add(WifiBlacklist(key=key, created=utcnow))
                remove_wifi.delay(list(moving_keys))
                session.commit()
            return moving_keys
    except IntegrityError as exc:  # pragma: no cover
        logger.exception('error')
        return []
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def remove_wifi(self, wifi_keys):
    wifi_keys = set(wifi_keys)
    try:
        with self.db_session() as session:
            query = session.query(Wifi).filter(
                Wifi.key.in_(wifi_keys))
            wifis = query.delete(synchronize_session=False)
            session.commit()
        return wifis
    except IntegrityError as exc:  # pragma: no cover
        logger.exception('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def cell_location_update(self, min_new=10, max_new=100, batch=10):
    try:
        cells = []
        with self.db_session() as session:
            query = session.query(Cell).filter(
                Cell.new_measures >= min_new).filter(
                Cell.new_measures < max_new).limit(batch)
            cells = query.all()
            if not cells:
                return 0
            for cell in cells:
                query = session.query(
                    CellMeasure.lat, CellMeasure.lon).filter(
                    CellMeasure.radio == cell.radio).filter(
                    CellMeasure.mcc == cell.mcc).filter(
                    CellMeasure.mnc == cell.mnc).filter(
                    CellMeasure.lac == cell.lac).filter(
                    CellMeasure.cid == cell.cid)
                # only take the last X new_measures
                query = query.order_by(
                    CellMeasure.created.desc()).limit(
                    cell.new_measures)
                measures = query.all()
                length = len(measures)
                new_lat = sum([w[0] for w in measures]) // length
                new_lon = sum([w[1] for w in measures]) // length
                if not (cell.lat or cell.lon):
                    cell.lat = new_lat
                    cell.lon = new_lon
                else:
                    # pre-existing location data
                    total = cell.total_measures
                    old_length = total - cell.new_measures
                    cell.lat = ((cell.lat * old_length) +
                                (new_lat * length)) // total
                    cell.lon = ((cell.lon * old_length) +
                                (new_lon * length)) // total
                cell.new_measures = Cell.new_measures - length
            session.commit()
        return len(cells)
    except IntegrityError as exc:  # pragma: no cover
        logger.exception('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def wifi_location_update(self, min_new=10, max_new=100, batch=10):
    try:
        wifis = {}
        with self.db_session() as session:
            query = session.query(Wifi.key, Wifi).filter(
                Wifi.new_measures >= min_new).filter(
                Wifi.new_measures < max_new).limit(batch)
            wifis = dict(query.all())
            if not wifis:
                return 0
            # TODO: This gets all measures and not just the X newest
            query = session.query(WifiMeasure).filter(
                WifiMeasure.key.in_(wifis.keys()))
            wifi_measures = defaultdict(list)
            for measure in query.all():
                wifi_measures[measure.key].append(measure)
            for wifi_key, wifi in wifis.items():
                measures = wifi_measures[wifi_key]
                # only take the last X new_measures
                measures = sorted(
                    measures, key=attrgetter('created'), reverse=True)
                measures = measures[:wifi.new_measures]
                length = len(measures)
                new_lat = sum([w.lat for w in measures]) // length
                new_lon = sum([w.lon for w in measures]) // length
                if not (wifi.lat or wifi.lon):
                    wifi.lat = new_lat
                    wifi.lon = new_lon
                else:
                    # pre-existing location data
                    total = wifi.total_measures
                    old_length = total - wifi.new_measures
                    wifi.lat = ((wifi.lat * old_length) +
                                (new_lat * length)) // total
                    wifi.lon = ((wifi.lon * old_length) +
                                (new_lon * length)) // total
                wifi.new_measures = Wifi.new_measures - length
            session.commit()
        return len(wifis)
    except IntegrityError as exc:  # pragma: no cover
        logger.exception('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)
