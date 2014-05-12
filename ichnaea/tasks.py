from contextlib import contextmanager
from contextlib import closing
from datetime import datetime
from datetime import timedelta
import tempfile
import hashlib
import os
import csv
import shutil
from zipfile import ZipFile, ZIP_DEFLATED


from ichnaea.backup import S3Backend
from celery import Task
from kombu.serialization import (
    dumps as kombu_dumps,
    loads as kombu_loads,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from ichnaea.db import db_worker_session
from ichnaea.heka_logging import (
    get_heka_client,
    RAVEN_ERROR,
)
from ichnaea.models import (
    Cell,
    CellKey,
    CellBlacklist,
    CellMeasure,
    CellMeasureBlock,
    CellMeasureCheckPoint,
    Wifi,
    WifiBlacklist,
    WifiMeasure,
    join_cellkey,
    to_cellkey,
    to_degrees,
    from_degrees,
    CELLID_LAC,
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
    now = datetime.utcnow()
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

    max_cm_id = None
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
                    lat_lons = [(m.lat, m.lon) for m in measures]
                    calculate_new_position(cell, lat_lons, moving_cells,
                                           CELL_MAX_DIST_KM,
                                           backfill=False)
                    update_enclosing_lac(session, cell)

                    max_cm_id = max([m.id for m in measures])

            if moving_cells:
                # some cells found to be moving too much
                mark_moving_cells(session, moving_cells)

            if max_cm_id:
                cm_cp = CellMeasureCheckPoint(cell_measure_id=max_cm_id)
                session.add(cm_cp)
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
        # if there's a lot of unprocessed new measures, forget them
        # and only retain the ones we still have the underlying measures for
        if u.new_measures > u.total_measures:
            u.new_measures = u.total_measures
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
            Cell.cid != CELLID_LAC)

        cells = q.all()
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


@contextmanager
def selfdestruct_tempdir(s3_key):
    short_name = os.path.split(s3_key)[-1]

    base_path = tempfile.mkdtemp()

    s3_path = os.path.join(tempfile.mkdtemp(), short_name)
    try:
        zip_path = os.path.join(base_path, s3_path)
        yield base_path, zip_path
    finally:
        try:
            with closing(ZipFile(zip_path, "w", ZIP_DEFLATED)) as z:
                for root, dirs, files in os.walk(base_path):
                    for fn in files:
                        absfn = os.path.join(root, fn)
                        zip_fn = absfn[len(base_path)+len(os.sep):]
                        z.write(absfn, zip_fn)
        finally:
            shutil.rmtree(base_path)


@celery.task(base=DatabaseTask, bind=True)
def write_s3_backups(self, cleanup_zip=True):
    """
    Iterate over each of the CellMeasureblock records that aren't
    backed up yet and back them up.

    Assume that this is running in a single task
    """
    zips = []
    utcnow = datetime.utcnow()
    with self.db_session() as session:
        query = session.query(CellMeasureBlock)
        query = query.filter(CellMeasureBlock.archive_date == None)  # NOQA
        query = query.order_by(CellMeasureBlock.end_cell_measure_id)
        for cmb in query.all():
            cmb.s3_key = '%s/CellMeasure_%d_%d.zip' % (utcnow.strftime("%Y%m"),
                                               cmb.start_cell_measure_id,
                                               cmb.end_cell_measure_id)

            with selfdestruct_tempdir(cmb.s3_key) as (tmp_path, zip_path):
                rset = session.execute("select * from alembic_version")
                rev = rset.first()[0]
                with open(os.path.join(tmp_path,
                                       'alembic_revision.txt'), 'w') as f:
                    f.write('%s\n' % rev)

                cm_fname = os.path.join(tmp_path, 'cell_measure.csv')

                cm_query = session.query(CellMeasure)
                cm_query = cm_query.filter(
                    CellMeasure.id >= cmb.start_cell_measure_id)
                cm_query = cm_query.filter(
                    CellMeasure.id <= cmb.end_cell_measure_id)

                col_names = None
                with open(cm_fname, 'w') as f:
                    csv_out = csv.writer(f, dialect='excel')
                    for i, row in enumerate(cm_query.all()):
                        if i == 0:
                            col_names = [c.name for c in row.__table__.columns]
                            csv_out.writerow(col_names)
                            pass
                        data_row = [getattr(row, cname) for cname in col_names]
                        csv_out.writerow(data_row)

            sha = hashlib.sha1()
            sha.update(open(zip_path, 'rb').read())

            cmb.archive_sha = sha.hexdigest()
            try:
                s3 = S3Backend(self.heka_client)
                if not s3.backup_and_check(cmb.s3_key, zip_path):
                    continue

                """
                TODO: move this into a separate task
                del_query = session.query(CellMeasure)
                del_query = del_query.filter(
                    CellMeasure.id >= cmb.start_cell_measure_id)
                del_query = query.filter(
                    CellMeasure.id <= cmb.end_cell_measure_id)
                del_query.delete()
                """
            finally:
                if cleanup_zip:
                    if os.path.exists(zip_path):
                        os.unlink(zip_path)
                else:
                    zips.append(zip_path)

            session.add(cmb)
            session.commit()
    return zips


@celery.task(base=DatabaseTask, bind=True)
def schedule_measure_archival(self):
    """
    This just looks at the CellMeasureCheckPoint table and adds an
    entry into CellMeasureBlock to schedule archival
    """
    with self.db_session() as session:
        query = session.query(CellMeasureCheckPoint.cell_measure_id)
        query = query.order_by(CellMeasureCheckPoint.cell_measure_id.desc())
        query = query.limit(1)
        records = query.all()
        if not len(records):
            return
        max_cell_measure_id = records[0][0]

        query = session.query(CellMeasureBlock.end_cell_measure_id)
        query = query.order_by(CellMeasureBlock.end_cell_measure_id.desc())
        query = query.limit(1)
        records = query.all()
        if len(records):
            last_cell_measure_id = records[0][0]
        else:
            last_cell_measure_id = 0

        total_entries_to_journal = max_cell_measure_id - last_cell_measure_id
        blocks = []
        if total_entries_to_journal > 0:
            # We have new entries to file
            from ichnaea import config
            conf = config()
            batch_size = int(conf.get('ichnaea', 'archive_batch_size'))
            while total_entries_to_journal > batch_size:
                entries_to_journal = min(batch_size, total_entries_to_journal)
                total_entries_to_journal -= entries_to_journal

                start = last_cell_measure_id + 1
                end = start + entries_to_journal - 1

                cm_blk = CellMeasureBlock(start_cell_measure_id=start,
                                          end_cell_measure_id=end)
                blocks.append((cm_blk.start_cell_measure_id,
                               cm_blk.end_cell_measure_id))
                session.add(cm_blk)
        session.commit()
        return blocks
