from datetime import datetime
from datetime import timedelta

from celery import Task
from celery.utils.log import get_task_logger
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
    acks_late = False
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
        with self.heka_client.timer("task." + self.shortname):
            result = super(DatabaseTask, self).__call__(*args, **kw)
        return result

    def db_session(self):
        # returns a context manager
        return db_worker_session(self.app.db_master)

    @property
    def heka_client(self):
        return get_client('ichnaea')


def daily_task_days(ago):
    today = datetime.utcnow().date()
    day = today - timedelta(days=ago)
    max_day = day + timedelta(days=1)
    return day, max_day


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


def update_extreme_values(model, latitudes, longitudes):
    # update max/min lat/lon columns
    extremes = {
        'max_lat': (max, latitudes),
        'min_lat': (min, latitudes),
        'max_lon': (max, longitudes),
        'min_lon': (min, longitudes),
    }
    for name, (func, values) in extremes.items():
        new = func(values)
        old = getattr(model, name, None)
        if old is not None:
            setattr(model, name, func(old, new))
        else:
            setattr(model, name, new)


def calculate_new_cell_position(cell, measures, backfill=True):
    # if backfill is true, we work on older measures for which
    # the new/total counters where never updated
    length = len(measures)
    latitudes = [w[0] for w in measures]
    longitudes = [w[1] for w in measures]
    new_lat = sum(latitudes) // length
    new_lon = sum(longitudes) // length

    if backfill:
        new_total = cell.total_measures + length
        old_length = cell.total_measures
        # update total to account for new measures
        # new counter never got updated to include the measures
        cell.total_measures = new_total
    else:
        new_total = cell.total_measures
        old_length = new_total - cell.new_measures
        # decrease new counter, total is already correct
        cell.new_measures = Cell.new_measures - length

    if not (cell.lat or cell.lon):
        cell.lat = new_lat
        cell.lon = new_lon
    else:
        # pre-existing location data
        cell.lat = ((cell.lat * old_length) +
                    (new_lat * length)) // new_total
        cell.lon = ((cell.lon * old_length) +
                    (new_lon * length)) // new_total

    # update max/min lat/lon columns
    update_extreme_values(cell, latitudes, longitudes)


@celery.task(base=DatabaseTask, bind=True)
def backfill_cell_location_update(self, new_cell_measures):
    try:
        cells = []
        with self.db_session() as session:
            for tower_tuple, cell_measure_ids in new_cell_measures.items():
                radio, mcc, mnc, lac, cid = tower_tuple
                query = session.query(Cell).filter(
                    Cell.radio == radio).filter(
                    Cell.mcc == mcc).filter(
                    Cell.mnc == mnc).filter(
                    Cell.lac == lac).filter(
                    Cell.cid == cid)

                cells = query.all()

                if not cells:
                    # This case shouldn't actually occur. The
                    # backfill_cell_location_update is only called
                    # when CellMeasure records are matched against
                    # known Cell records.
                    continue

                for cell in cells:
                    measures = session.query(  # NOQA
                        CellMeasure.lat, CellMeasure.lon).filter(
                        CellMeasure.id.in_(cell_measure_ids)).all()

                    if measures:
                        calculate_new_cell_position(
                            cell, measures, backfill=True)

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
                # skip cells with a missing lac/cid
                if cell.lac == -1 or cell.cid == -1:
                    continue

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

                if measures:
                    calculate_new_cell_position(cell, measures, backfill=False)

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

                # decrease new value to mark as done
                wifi.new_measures = Wifi.new_measures - length
                # update max/min lat/lon columns
                update_extreme_values(wifi, latitudes, longitudes)

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
