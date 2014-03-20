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
    CellBlacklist,
    CellMeasure,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
    to_degrees,
)
from ichnaea.worker import celery
from ichnaea.geocalc import distance
from collections import namedtuple

WIFI_MAX_DIST_KM = 5
CELL_MAX_DIST_KM = 150

CellKey = namedtuple('CellKey', 'radio mcc mnc lac cid')


def to_cellkey(obj):
    """
    Construct a CellKey from any object with the requisite 5 named cell fields.
    """
    if isinstance(obj, dict):
        return CellKey(radio=obj['radio'],
                       mcc=obj['mcc'],
                       mnc=obj['mnc'],
                       lac=obj['lac'],
                       cid=obj['cid'])
    else:
        return CellKey(radio=obj.radio,
                       mcc=obj.mcc,
                       mnc=obj.mnc,
                       lac=obj.lac,
                       cid=obj.cid)


def join_cellkey(model, k):
    """
    Return an sqlalchemy equality criterion for joining on the cell 5-tuple.
    Should be spliced into a query filter call like so:
    ``session.query(Cell).filter(*join_cellkey(Cell, k))``
    """
    return (model.radio == k.radio,
            model.mcc == k.mcc,
            model.mnc == k.mnc,
            model.lac == k.lac,
            model.cid == k.cid)


def get_heka_client():
    return get_client('ichnaea')


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
        return get_heka_client()


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


@celery.task(base=DatabaseTask, bind=True)
def remove_cell(self, cell_keys):
    cells_removed = 0
    try:
        with self.db_session() as session:
            for k in cell_keys:
                key = to_cellkey(k)
                query = session.query(Cell).filter(*join_cellkey(Cell, key))
                cells_removed += query.delete(synchronize_session=False)
            session.commit()
        return cells_removed
    except IntegrityError as exc:  # pragma: no cover
        self.heka_client.raven('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


def calculate_new_position(station, measures, moving_stations,
                           max_dist_km, backfill=True):
    # if backfill is true, we work on older measures for which
    # the new/total counters where never updated
    length = len(measures)
    latitudes = [w[0] for w in measures]
    longitudes = [w[1] for w in measures]
    new_lat = sum(latitudes) // length
    new_lon = sum(longitudes) // length

    if station.lat and station.lon:
        latitudes.append(station.lat)
        longitudes.append(station.lon)
        existing_station = True
    else:
        station.lat = new_lat
        station.lon = new_lon
        existing_station = False

    # calculate extremes of measures, existing location estimate
    # and existing extreme values
    def extreme(vals, attr, function):
        new = function(vals)
        old = getattr(station, attr, None)
        if old is not None:
            return function(new, old)
        else:
            return new

    min_lat = extreme(latitudes, 'min_lat', min)
    min_lon = extreme(longitudes, 'min_lon', min)
    max_lat = extreme(latitudes, 'max_lat', max)
    max_lon = extreme(longitudes, 'max_lon', max)

    # calculate sphere-distance from opposite corners of
    # bounding box containing current location estimate
    # and new measurements; if too big, station is moving
    box_dist = distance(to_degrees(min_lat), to_degrees(min_lon),
                        to_degrees(max_lat), to_degrees(max_lon))

    if existing_station:

        if box_dist > max_dist_km:
            # add to moving list, return early without updating
            # station since it will be deleted by caller momentarily
            moving_stations.add(station)
            return

        if backfill:
            new_total = station.total_measures + length
            old_length = station.total_measures
            # update total to account for new measures
            # new counter never got updated to include the measures
            station.total_measures = new_total
        else:
            new_total = station.total_measures
            old_length = new_total - station.new_measures

        station.lat = ((station.lat * old_length) +
                       (new_lat * length)) // new_total
        station.lon = ((station.lon * old_length) +
                       (new_lon * length)) // new_total

    if not backfill:
        # decrease new counter, total is already correct
        # in the backfill case new counter was never increased
        station.new_measures = station.new_measures - length

    # update max/min lat/lon columns
    station.min_lat = min_lat
    station.min_lon = min_lon
    station.max_lat = max_lat
    station.max_lon = max_lon

    # give radio-range estimate, in meters, as half bounding box diagonal
    station.range = int(round((box_dist * 1000.0) / 2.0))


@celery.task(base=DatabaseTask, bind=True)
def backfill_cell_location_update(self, new_cell_measures):
    try:
        cells = []
        new_cell_measures = dict(new_cell_measures)
        with self.db_session() as session:
            for tower_tuple, cell_measure_ids in new_cell_measures.items():
                query = session.query(Cell).filter(
                    *join_cellkey(Cell, CellKey(*tower_tuple)))
                cells = query.all()

                if not cells:
                    # This case shouldn't actually occur. The
                    # backfill_cell_location_update is only called
                    # when CellMeasure records are matched against
                    # known Cell records.
                    continue

                moving_cells = set()
                for cell in cells:
                    measures = session.query(  # NOQA
                        CellMeasure.lat, CellMeasure.lon).filter(
                        CellMeasure.id.in_(cell_measure_ids)).all()

                    if measures:
                        calculate_new_position(cell, measures, moving_cells,
                                               CELL_MAX_DIST_KM,
                                               backfill=True)

                if moving_cells:
                    # some cells found to be moving too much
                    mark_moving_cells(session, moving_cells)

            session.commit()
        return (len(cells), len(moving_cells))
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
            moving_cells = set()
            for cell in cells:
                # skip cells with a missing lac/cid
                if cell.lac == -1 or cell.cid == -1:
                    continue

                query = session.query(
                    CellMeasure.lat, CellMeasure.lon).filter(
                    *join_cellkey(CellMeasure, cell))
                # only take the last X new_measures
                query = query.order_by(
                    CellMeasure.created.desc()).limit(
                    cell.new_measures)
                measures = query.all()

                if measures:
                    calculate_new_position(cell, measures, moving_cells,
                                           CELL_MAX_DIST_KM,
                                           backfill=False)

            if moving_cells:
                # some cells found to be moving too much
                mark_moving_cells(session, moving_cells)

            session.commit()
        return (len(cells), len(moving_cells))
    except IntegrityError as exc:  # pragma: no cover
        self.heka_client.raven('error')
        return 0
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


def mark_moving_wifis(session, moving_wifis):
    moving_keys = set([wifi.key for wifi in moving_wifis])
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
    get_heka_client().incr("items.blacklisted.wifi_moving",
                           len(moving_keys))
    remove_wifi.delay(list(moving_keys))


def mark_moving_cells(session, moving_cells):
    moving_keys = []
    blacklist = set()
    for cell in moving_cells:
        query = session.query(CellBlacklist).filter(
            *join_cellkey(CellBlacklist, cell))
        b = query.first()
        if b is None:
            key = to_cellkey(cell)._asdict()
            blacklist.add(CellBlacklist(**key))
            moving_keys.append(key)

    get_heka_client().incr("items.blacklisted.cell_moving",
                           len(moving_keys))
    session.add_all(blacklist)
    remove_cell.delay(moving_keys)


@celery.task(base=DatabaseTask, bind=True)
def wifi_location_update(self, min_new=10, max_new=100, batch=10):
    # TODO: this doesn't take into account wifi AP's which have
    # permanently moved after a certain date

    try:
        wifis = {}
        with self.db_session() as session:
            query = session.query(Wifi.key, Wifi).filter(
                Wifi.new_measures >= min_new).filter(
                Wifi.new_measures < max_new).limit(batch)
            wifis = dict(query.all())
            if not wifis:
                return 0
            moving_wifis = set()
            for wifi_key, wifi in wifis.items():
                # only take the last X new_measures
                measures = session.query(
                    WifiMeasure.lat, WifiMeasure.lon).filter(
                    WifiMeasure.key == wifi_key).order_by(
                    WifiMeasure.created.desc()).limit(
                    wifi.new_measures).all()
                if measures:
                    calculate_new_position(wifi, measures, moving_wifis,
                                           WIFI_MAX_DIST_KM, backfill=False)

            if moving_wifis:
                # some wifis found to be moving too much
                mark_moving_wifis(session, moving_wifis)

            session.commit()
        return (len(wifis), len(moving_wifis))
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

            n = trim_excessive_data(session=session,
                                    unique_model=Wifi,
                                    measure_model=WifiMeasure,
                                    join_measure=join_measure,
                                    delstat='deleted_wifi',
                                    max_measures=max_measures,
                                    min_age_days=min_age_days,
                                    batch=batch)
            self.heka_client.incr("items.dropped.wifi_trim_excessive", n)
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def cell_trim_excessive_data(self, max_measures, min_age_days=7, batch=10):
    try:
        with self.db_session() as session:
            join_measure = lambda u: join_cellkey(CellMeasure, u)

            n = trim_excessive_data(session=session,
                                    unique_model=Cell,
                                    measure_model=CellMeasure,
                                    join_measure=join_measure,
                                    delstat='deleted_cell',
                                    max_measures=max_measures,
                                    min_age_days=min_age_days,
                                    batch=batch)
            self.heka_client.incr("items.dropped.cell_trim_excessive", n)
    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def read_database_gauges(self):
    try:
        with self.db_session() as session:

            def gauge(name, q):
                v = q.all()
                if v is None:
                    v = 0
                else:
                    v = v[0]
                self.heka_client.gauge(name, v)

            def count_model(model):
                return session.query(func.count(model))

            gauge("gauges.models.Cell", count_model(Cell.id))
            gauge("gauges.models.CellBlacklist", count_model(CellBlacklist.id))
            gauge("gauges.models.CellMeasure", count_model(CellMeasure.id))
            gauge("gauges.models.Wifi", count_model(Wifi.id))
            gauge("gauges.models.WifiBlacklist", count_model(WifiBlacklist.id))
            gauge("gauges.models.WifiMeasure", count_model(WifiMeasure.id))

    except Exception as exc:  # pragma: no cover
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def read_psutil_gauges(self):
    import psutil
    import platform

    node = platform.node()

    def gauge(name, v):
        self.heka_client.gauge("gauges.system.%s.%s" % (node, name), v)

    gauge("cpu_percent", psutil.cpu_percent())

    vm = psutil.virtual_memory()
    gauge("mem_used", vm.used)
    gauge("mem_percent", vm.percent)

    du = psutil.disk_usage('/')
    gauge("disk_used", du.used)
    gauge("disk_percent", du.percent)

    nio = psutil.net_io_counters()
    gauge("net_bytes_sent", nio.bytes_sent)
    gauge("net_bytes_recv", nio.bytes_recv)
    gauge("net_errin", nio.errin)
    gauge("net_errout", nio.errout)

    dio = psutil.disk_io_counters()
    gauge("disk_read_bytes", dio.read_bytes)
    gauge("disk_write_bytes", dio.write_bytes)
    gauge("disk_read_time", dio.read_time)
    gauge("disk_write_time", dio.write_time)
