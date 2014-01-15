from datetime import datetime
from datetime import timedelta

from celery import Task
from celery.utils.log import get_task_logger
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

from heka.holder import get_client


class DatabaseTask(Task):
    abstract = True
    acks_late = True
    ignore_result = True
    max_retries = 3

    _shortname = None

    @property
    def shortname(self):
        short = self._shortname
        if short is None:
            # strip off ichnaea prefix and tasks module
            segments = self.name.split('.')
            segments = [s for s in segments if s not in ('ichnaea', 'tasks')]
            short = self._shortname = '.'.join(segments)
        return short

    def __call__(self, *args, **kw):
        with get_client('ichnaea').timer("task." + self.shortname):
            result = super(DatabaseTask, self).__call__(*args, **kw)
        return result

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
def backfill_cell_location_update(self, new_cell_measures):
    try:
        cells = []
        with self.db_session() as session:
            for tower_tuple in new_cell_measures.keys():
                radio, mcc, mnc, lac, cid = tower_tuple
                query = session.query(Cell).filter(
                    Cell.radio == radio).filter(
                    Cell.mcc == mcc).filter(
                    Cell.mnc == mnc).filter(
                    Cell.lac == lac).filter(
                    Cell.cid == cid)

                cells = query.all()

                if not cells:
                    continue

                for cell in cells:
                    cellmeasure_ids = new_cell_measures[tower_tuple]

                    query = None
                    for id in cellmeasure_ids:
                        sub_query = session.query(CellMeasure.lat, CellMeasure.lon).filter(
                                                  CellMeasure.id == id)
                        if query is None:
                            query = sub_query
                        else:
                            query = sub_query
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


def mark_moving_wifis(session, moving_keys):
    utcnow = datetime.utcnow()
    query = session.query(WifiBlacklist.key).filter(
        WifiBlacklist.key.in_(moving_keys))
    already_blocked = set([a[0] for a in query.all()])
    moving_keys = moving_keys - already_blocked
    if not moving_keys:
        return
    for key in moving_keys:
        # on duplicate key, do a no-op change
        stmt = WifiBlacklist.__table__.insert(
            on_duplicate='created=created').values(
            key=key, created=utcnow)
        session.execute(stmt)
    remove_wifi.delay(list(moving_keys))


@celery.task(base=DatabaseTask, bind=True)
def wifi_location_update(self, min_new=10, max_new=100, batch=10):
    # TODO: this doesn't take into account wifi AP's which have
    # permanently moved after a certain date

    # maximum difference of two decimal places, ~5km at equator
    # or ~2km at 67 degrees north
    MAX_DIFF = 500000
    try:
        wifis = {}
        with self.db_session() as session:
            query = session.query(Wifi.key, Wifi).filter(
                Wifi.new_measures >= min_new).filter(
                Wifi.new_measures < max_new).limit(batch)
            wifis = dict(query.all())
            if not wifis:
                return 0
            moving_keys = set()
            for wifi_key, wifi in wifis.items():
                # only take the last X new_measures
                measures = session.query(
                    WifiMeasure.lat, WifiMeasure.lon).filter(
                    WifiMeasure.key == wifi_key).order_by(
                    WifiMeasure.created.desc()).limit(
                    wifi.new_measures).all()
                length = len(measures)
                latitudes = [w[0] for w in measures]
                longitudes = [w[1] for w in measures]
                new_lat = sum(latitudes) // length
                new_lon = sum(longitudes) // length
                if not (wifi.lat or wifi.lon):
                    # no prior position
                    wifi.lat = new_lat
                    wifi.lon = new_lon
                else:
                    # pre-existing location data, check for moving wifi
                    # add old lat/lon to the candidate list
                    latitudes.append(wifi.lat)
                    longitudes.append(wifi.lon)
                    lat_diff = abs(max(latitudes) - min(latitudes))
                    lon_diff = abs(max(longitudes) - min(longitudes))
                    if lat_diff >= MAX_DIFF or lon_diff >= MAX_DIFF:
                        # add to moving list, skip further updates
                        moving_keys.add(wifi_key)
                        continue
                    total = wifi.total_measures
                    old_length = total - wifi.new_measures
                    wifi.lat = ((wifi.lat * old_length) +
                                (new_lat * length)) // total
                    wifi.lon = ((wifi.lon * old_length) +
                                (new_lon * length)) // total
                wifi.new_measures = Wifi.new_measures - length
            if moving_keys:
                # some wifi's found to be moving too much
                mark_moving_wifis(session, moving_keys)
            session.commit()
        return (len(wifis), len(moving_keys))
    except IntegrityError as exc:  # pragma: no cover
        logger.exception('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)
