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
    WifiBlacklist,
    WifiMeasure,
    Stat,
)
from ichnaea.decimaljson import decode_datetime
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
                remove_wifi_measure.delay(moving_keys)
                session.commit()
            return moving_keys
    except IntegrityError as exc:  # pragma: no cover
        # TODO log error
        return []
    except Exception as exc:  # pragma: no cover
        raise blacklist_moving_wifis.retry(exc=exc)


@celery.task(base=DatabaseTask, ignore_result=True)
def insert_wifi_measure(measure_data, entries):
    wifi_measures = []
    wifi_keys = set([e['key'] for e in entries])
    try:
        with insert_wifi_measure.db_session() as session:
            blacked = session.query(WifiBlacklist.key).filter(
                WifiBlacklist.key.in_(wifi_keys)).all()
            blacked = set([b[0] for b in blacked])
            for entry in entries:
                # skip blacklisted wifi AP's
                if entry['key'] in blacked:
                    continue
                # convert frequency into channel numbers and remove frequency
                freq = entry.pop('frequency', 0)
                # if no explicit channel was given, calculate
                if freq and not entry['channel']:
                    if 2411 < freq < 2473:
                        # 2.4 GHz band
                        entry['channel'] = (freq - 2407) // 5
                    elif 5169 < freq < 5826:
                        # 5 GHz band
                        entry['channel'] = (freq - 5000) // 5
                wifi_measure = WifiMeasure(
                    measure_id=measure_data['id'],
                    created=decode_datetime(measure_data.get('created', '')),
                    lat=measure_data['lat'],
                    lon=measure_data['lon'],
                    time=decode_datetime(measure_data.get('time', '')),
                    accuracy=measure_data.get('accuracy', 0),
                    altitude=measure_data.get('altitude', 0),
                    altitude_accuracy=measure_data.get('altitude_accuracy', 0),
                    id=entry.get('id', None),
                    key=entry['key'],
                    channel=entry.get('channel', 0),
                    signal=entry.get('signal', 0),
                )
                wifi_measures.append(wifi_measure)

            session.add_all(wifi_measures)
            session.commit()
        return len(wifi_measures)
    except IntegrityError as exc:
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise insert_wifi_measure.retry(exc=exc)


@celery.task(base=DatabaseTask, ignore_result=True)
def remove_wifi_measure(wifi_keys):
    wifi_keys = set(wifi_keys)
    try:
        result = 0
        with remove_wifi_measure.db_session() as session:
            query = session.query(WifiMeasure).filter(
                WifiMeasure.key.in_(wifi_keys))
            result = query.delete(synchronize_session=False)
            session.commit()
        return result
    except IntegrityError as exc:  # pragma: no cover
        # TODO log error
        return 0
    except Exception as exc:  # pragma: no cover
        raise remove_wifi_measure.retry(exc=exc)
