from datetime import datetime
from datetime import timedelta

from celery import Task
from kombu.serialization import (
    dumps as kombu_dumps,
    loads as kombu_loads,
)
import pytz
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from ichnaea.db import db_worker_session
from ichnaea.heka_logging import (
    get_heka_client,
    RAVEN_ERROR,
)
from ichnaea.models import (
    CELLID_LAC,
    Cell,
    CellBlacklist,
    CellKey,
    CellMeasure,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
    from_degrees,
    join_cellkey,
    join_wifikey,
    to_cellkey,
    to_wifikey,
    to_degrees,
)
from ichnaea.worker import celery
from ichnaea.geocalc import distance, centroid, range_to_points

WIFI_MAX_DIST_KM = 5
CELL_MAX_DIST_KM = 150


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
            # It's easy enough to put datetime, set or other
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
    wifi_keys = set([w['key'] for w in wifi_keys])
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
                cells_removed += query.delete()

                # Either schedule an update to the enclosing LAC or, if
                # we just removed the last cell in the LAC, remove the LAC
                # entirely.
                query = session.query(func.count(Cell.id)).filter(
                    Cell.radio == key.radio,
                    Cell.mcc == key.mcc,
                    Cell.mnc == key.mnc,
                    Cell.lac == key.lac,
                    Cell.cid != CELLID_LAC)

                c = query.first()
                assert c is not None
                n = int(c[0])
                query = session.query(Cell).filter(
                    Cell.radio == key.radio,
                    Cell.mcc == key.mcc,
                    Cell.mnc == key.mnc,
                    Cell.lac == key.lac,
                    Cell.cid == CELLID_LAC)
                if n < 1:
                    query.delete()
                else:
                    query.update({'new_measures': '1'})

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
            old_length = new_total - length

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

    # give radio-range estimate between extreme values and centroid
    ctr = (to_degrees(station.lat), to_degrees(station.lon))
    points = [(to_degrees(min_lat), to_degrees(min_lon)),
              (to_degrees(min_lat), to_degrees(max_lon)),
              (to_degrees(max_lat), to_degrees(min_lon)),
              (to_degrees(max_lat), to_degrees(max_lon))]

    station.range = range_to_points(ctr, points) * 1000.0


def update_enclosing_lac(session, cell):
    now = datetime.utcnow().replace(tzinfo=pytz.UTC)
    stmt = Cell.__table__.insert(
        on_duplicate='new_measures = new_measures + 1'
    ).values(
        radio=cell.radio, mcc=cell.mcc, mnc=cell.mnc, lac=cell.lac,
        cid=CELLID_LAC, lat=cell.lat, lon=cell.lon, range=cell.range,
        new_measures=1, total_measures=0, created=now)
    session.execute(stmt)


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
                        update_enclosing_lac(session, cell)

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
                Cell.new_measures < max_new).filter(
                Cell.cid != CELLID_LAC).limit(batch)
            cells = query.all()
            if not cells:
                return 0
            moving_cells = set()
            for cell in cells:
                # skip cells with a missing lac/cid
                # or virtual LAC cells
                if cell.lac == -1 or cell.cid == -1 or \
                   cell.cid == CELLID_LAC:
                    continue

                query = session.query(
                    CellMeasure.lat, CellMeasure.lon, CellMeasure.id).filter(
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
                    update_enclosing_lac(session, cell)

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


def mark_moving_station(session, blacklist_model, station_type,
                        to_key, join_key, moving_stations,
                        remove_station):
    moving_keys = []
    blacklist = set()
    utcnow = datetime.utcnow().replace(tzinfo=pytz.UTC)
    for station in moving_stations:
        key = to_key(station)
        query = session.query(blacklist_model).filter(
            *join_key(blacklist_model, key))
        b = query.first()
        if b:
            b.time = utcnow
            b.count += 1
        else:
            d = key._asdict()
            b = blacklist_model(**d)
            moving_keys.append(d)
        blacklist.add(b)

    session.add_all(blacklist)

    if moving_keys:
        get_heka_client().incr("items.blacklisted.%s_moving" % station_type,
                               len(moving_keys))
        remove_station.delay(moving_keys)


def mark_moving_wifis(session, moving_wifis):
    mark_moving_station(session,
                        blacklist_model=WifiBlacklist,
                        station_type="wifi",
                        to_key=to_wifikey,
                        join_key=join_wifikey,
                        moving_stations=moving_wifis,
                        remove_station=remove_wifi)


def mark_moving_cells(session, moving_cells):
    mark_moving_station(session,
                        blacklist_model=CellBlacklist,
                        station_type="cell",
                        to_key=to_cellkey,
                        join_key=join_cellkey,
                        moving_stations=moving_cells,
                        remove_station=remove_cell)


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


@celery.task(base=DatabaseTask, bind=True)
def scan_lacs(self, batch=100):
    """
    Find cell LACs that have changed and update the bounding box.

    """
    with self.db_session() as session:
        q = session.query(Cell).filter(
            Cell.cid == CELLID_LAC).filter(
            Cell.new_measures > 0).limit(batch)
        lacs = q.all()
        n = len(lacs)
        for lac in lacs:
            update_lac.delay(lac.radio, lac.mcc,
                             lac.mnc, lac.lac)
        session.commit()
        return n


@celery.task(base=DatabaseTask, bind=True)
def update_lac(self, radio, mcc, mnc, lac):

    with self.db_session() as session:

        # Select all the cells in this LAC that aren't the virtual
        # cell itself, and derive a bounding box for them.

        q = session.query(Cell).filter(
            Cell.radio == radio).filter(
            Cell.mcc == mcc).filter(
            Cell.mnc == mnc).filter(
            Cell.lac == lac).filter(
            Cell.cid != CELLID_LAC).filter(
            Cell.new_measures == 0).filter(
            Cell.lat.isnot(None)).filter(
            Cell.lon.isnot(None))

        cells = q.all()
        if len(cells) == 0:
            return

        points = [(to_degrees(c.lat),
                   to_degrees(c.lon)) for c in cells]
        min_lat = to_degrees(min([c.min_lat for c in cells]))
        min_lon = to_degrees(min([c.min_lon for c in cells]))
        max_lat = to_degrees(max([c.max_lat for c in cells]))
        max_lon = to_degrees(max([c.max_lon for c in cells]))

        bbox_points = [(min_lat, min_lon),
                       (min_lat, max_lon),
                       (max_lat, min_lon),
                       (max_lat, max_lon)]

        ctr = centroid(points)
        rng = range_to_points(ctr, bbox_points)

        # switch units back to DB preferred centimicrodegres angle
        # and meters distance.
        ctr_lat = from_degrees(ctr[0])
        ctr_lon = from_degrees(ctr[1])
        rng = int(round(rng * 1000.0))

        # Now create or update the LAC virtual cell

        q = session.query(Cell).filter(
            Cell.radio == radio).filter(
            Cell.mcc == mcc).filter(
            Cell.mnc == mnc).filter(
            Cell.lac == lac).filter(
            Cell.cid == CELLID_LAC)

        lac = q.first()

        if lac is None:
            lac = Cell(radio=radio,
                       mcc=mcc,
                       mnc=mnc,
                       lac=lac,
                       cid=CELLID_LAC,
                       lat=ctr_lat,
                       lon=ctr_lon,
                       range=rng)
        else:
            lac.new_measures = 0
            lac.lat = ctr_lat
            lac.lon = ctr_lon
            lac.range = rng

        session.commit()
