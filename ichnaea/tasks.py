from collections import defaultdict
from datetime import datetime
from datetime import timedelta
from operator import attrgetter

from celery import Task
from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ichnaea.db import db_worker_session
from ichnaea.models import (
    Wifi,
    WifiBlacklist,
    WifiMeasure,
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


def histogram_days(ago):
    today = datetime.utcnow().date()
    day = today - timedelta(days=ago)
    max_day = day + timedelta(days=1)
    return day, max_day


@celery.task(base=DatabaseTask, ignore_result=True)
def schedule_new_moving_wifi_analysis(ago=1, batch=1000):
    day, max_day = histogram_days(ago)
    try:
        with schedule_new_moving_wifi_analysis.db_session() as session:
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
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise schedule_new_moving_wifi_analysis.retry(exc=exc)


@celery.task(base=DatabaseTask, ignore_result=True)
def blacklist_moving_wifis(ago=1, offset=0, batch=1000):
    # TODO: this doesn't take into account wifi AP's which have
    # permanently moved after a certain date

    # maximum difference of two decimal places, ~1km at equator
    # or 500m at 67 degrees north
    max_difference = 100000
    day, max_day = histogram_days(ago)
    try:
        with blacklist_moving_wifis.db_session() as session:
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
                WifiMeasure.key.in_(new_wifis)).group_by(WifiMeasure.key)
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
        # TODO log error
        return []
    except Exception as exc:  # pragma: no cover
        raise blacklist_moving_wifis.retry(exc=exc)


@celery.task(base=DatabaseTask, ignore_result=True)
def remove_wifi(wifi_keys):
    wifi_keys = set(wifi_keys)
    try:
        with remove_wifi.db_session() as session:
            query = session.query(Wifi).filter(
                Wifi.key.in_(wifi_keys))
            wifis = query.delete(synchronize_session=False)
            query = session.query(WifiMeasure).filter(
                WifiMeasure.key.in_(wifi_keys))
            measures = query.delete(synchronize_session=False)
            session.commit()
        return (wifis, measures)
    except IntegrityError as exc:  # pragma: no cover
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise remove_wifi.retry(exc=exc)


@celery.task(base=DatabaseTask, ignore_result=True)
def wifi_location_update(min_new=10, max_new=100, batch=10):
    try:
        wifis = {}
        with wifi_location_update.db_session() as session:
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
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise wifi_location_update.retry(exc=exc)
