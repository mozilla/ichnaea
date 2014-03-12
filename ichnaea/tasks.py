from datetime import datetime
from datetime import timedelta

from celery import Task
from kombu.serialization import (
    dumps as kombu_dumps,
    loads as kombu_loads,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from heka.holder import get_client

from ichnaea.db import db_worker_session
from ichnaea.heka_logging import RAVEN_ERROR
from ichnaea.models import (
    Cell,
    CellMeasure,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
)
from ichnaea.worker import celery


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
            try:
                result = super(DatabaseTask, self).__call__(*args, **kw)
            except Exception:
                self.heka_client.raven(RAVEN_ERROR)
                raise
        return result

    def apply(self, *args, **kw):
        # This method is only used when calling tasks directly and blocking
        # on them. It's also used if always_eager is set, like in tests.
        # Using this in real code should be rare, so the extra overhead of
        # the check shouldn't matter.

        if self.app.conf.CELERY_ALWAYS_EAGER:
            # We do the extra check to make sure this was really used from
            # inside tests

            # We feed the task arguments through the de/serialization process
            # to make sure the arguments can indeed be serialized.
            # It's easy enough to put decimal, datetime, set or other
            # non-serializable objects into the task arguments
            task_args = isinstance(args, tuple) and args or tuple(args)
            serializer = self.app.conf.CELERY_TASK_SERIALIZER
            content_type, encoding, data = kombu_dumps(task_args, serializer)
            kombu_loads(data, content_type, encoding)

        return super(DatabaseTask, self).apply(*args, **kw)

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
        self.heka_client.raven('error')
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
    for name, (function, values) in extremes.items():
        new = function(values)
        old = getattr(model, name, None)
        if old is not None:
            setattr(model, name, function(old, new))
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
        self.heka_client.raven('error')
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
        self.heka_client.raven('error')
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
        self.heka_client.raven('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


def trim_excessive_data(session, unique_model, measure_model,
                        join_measure, delstat, max_measures,
                        min_age_days, batch):
    """
    Delete measurements of type `measure_model` when, for any given
    key-field `kname`, there are more than `max_measures` measurements.
    Avoid deleting any measurements at all younger than `min_age_days`,
    and only delete measurements from at most `batch` keys per call.
    Increment the deleted-measurements stat named `delstat` and decrement
    the `total_measurements` field of the associated `unique_model`, as
    side effects.
    """
    from ichnaea.content.tasks import incr_stat

    # generally: only work with rows that are older than a
    # date threshold, so that we are definitely not interfering
    # with periodic recent-stat calculations on incoming new data
    utcnow = datetime.utcnow()
    age_threshold = utcnow - timedelta(days=min_age_days)
    age_cond = measure_model.created < age_threshold

    # initial (fast) query to pull out those uniques that have
    # total_measures larger than max_measures; will refine this
    # set of keys subsequently by date-window.
    query = session.query(unique_model).filter(
        unique_model.total_measures > max_measures).limit(batch)
    uniques = query.all()
    counts = []

    # secondarily, refine set of candidate keys by explicitly
    # counting measurements on each key, within the expiration
    # date-window.
    for u in uniques:

        query = session.query(func.count(measure_model.id)).filter(
            *join_measure(u)).filter(
            age_cond)

        c = query.first()
        assert c is not None
        n = int(c[0])
        if n > max_measures:
            counts.append((u, n))

    if len(counts) == 0:
        return 0

    # finally, for each definitely over-measured key, find a
    # cutoff row and trim measurements to it
    for (u, count) in counts:

        # determine the oldest measure (smallest (date,id) pair) to
        # keep for each key
        start = count - max_measures
        (smallest_date_to_keep, smallest_id_to_keep) = session.query(
            measure_model.time, measure_model.id).filter(
            *join_measure(u)).filter(
            age_cond).order_by(
            measure_model.time, measure_model.id).slice(start, count).first()

        # delete measures with (date,id) less than that, so long as they're
        # older than the date window.
        n = session.query(
            measure_model).filter(
            *join_measure(u)).filter(
            age_cond).filter(
            measure_model.time <= smallest_date_to_keep).filter(
            measure_model.id < smallest_id_to_keep).delete()

        # decrement model.total_measures; increment stats[delstat]
        assert u.total_measures >= 0
        u.total_measures -= n
        incr_stat(session, delstat, n)

    session.commit()
    return n


@celery.task(base=DatabaseTask, bind=True)
def wifi_trim_excessive_data(self, max_measures, min_age_days=7, batch=10):
    try:
        with self.db_session() as session:
            join_measure = lambda u: (WifiMeasure.key == u.key, )

            trim_excessive_data(session=session,
                                unique_model=Wifi,
                                measure_model=WifiMeasure,
                                join_measure=join_measure,
                                delstat='deleted_wifi',
                                max_measures=max_measures,
                                min_age_days=min_age_days,
                                batch=batch)
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def cell_trim_excessive_data(self, max_measures, min_age_days=7, batch=10):
    try:
        with self.db_session() as session:
            join_measure = lambda u: (
                CellMeasure.radio == u.radio,
                CellMeasure.mcc == u.mcc,
                CellMeasure.mnc == u.mnc,
                CellMeasure.lac == u.lac,
                CellMeasure.cid == u.cid,
            )

            trim_excessive_data(session=session,
                                unique_model=Cell,
                                measure_model=CellMeasure,
                                join_measure=join_measure,
                                delstat='deleted_cell',
                                max_measures=max_measures,
                                min_age_days=min_age_days,
                                batch=batch)
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)
