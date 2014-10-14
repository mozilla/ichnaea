from contextlib import contextmanager
from zipfile import ZipFile, ZIP_DEFLATED
import csv
import os
import shutil
import tempfile

import pytz
from sqlalchemy import func

from ichnaea.async.task import DatabaseTask
from ichnaea.backup.s3 import S3Backend, compute_hash
from ichnaea.models import (
    Cell,
    CellMeasure,
    join_cellkey,
    MEASURE_TYPE_CODE,
    MEASURE_TYPE_CODE_INVERSE,
    MEASURE_TYPE_META,
    MeasureBlock,
    Wifi,
    WifiMeasure,
)
from ichnaea import util
from ichnaea.worker import celery


@contextmanager
def selfdestruct_tempdir(s3_key):
    """
    We need two temp directories to do this properly.

    The base_path is a temp directory that holds all the content that
    will go into our zip file. This is effectively a working
    directory that gets immediately deleted once the zip file is
    ready.

    The zip_path is the filename of the zip file that will get
    uploaded into S3. It is the responsibility of the caller of
    selfdestruct_tempdir to remove the zip_path and parent directory.
    """
    short_name = os.path.split(s3_key)[-1]

    base_path = tempfile.mkdtemp()
    s3_path = os.path.join(tempfile.mkdtemp(), short_name)
    try:
        zip_path = os.path.join(base_path, s3_path)
        yield base_path, zip_path
    finally:
        try:
            z = ZipFile(zip_path, "w", ZIP_DEFLATED)
            try:
                for root, dirs, files in os.walk(base_path):
                    for fn in files:
                        absfn = os.path.join(root, fn)
                        zip_fn = absfn[len(base_path) + len(os.sep):]
                        z.write(absfn, zip_fn)
            finally:
                z.close()
        finally:
            shutil.rmtree(base_path)


@celery.task(base=DatabaseTask, bind=True)
def write_cellmeasure_s3_backups(self,
                                 limit=100,
                                 batch=10000,
                                 countdown=300,
                                 cleanup_zip=True):
    measure_type = MEASURE_TYPE_CODE['cell']
    return write_measure_s3_backups(self,
                                    measure_type,
                                    limit=limit,
                                    batch=batch,
                                    countdown=countdown,
                                    cleanup_zip=cleanup_zip)


@celery.task(base=DatabaseTask, bind=True)
def write_wifimeasure_s3_backups(self,
                                 limit=100,
                                 batch=10000,
                                 countdown=300,
                                 cleanup_zip=True):
    measure_type = MEASURE_TYPE_CODE['wifi']
    return write_measure_s3_backups(self,
                                    measure_type,
                                    limit=limit,
                                    batch=batch,
                                    countdown=countdown,
                                    cleanup_zip=cleanup_zip)


def write_measure_s3_backups(self,
                             measure_type,
                             limit=100,
                             batch=10000,
                             countdown=300,
                             cleanup_zip=True):
    """
    Iterate over each of the measure block records that aren't
    backed up yet and back them up.
    """
    with self.db_session() as session:

        query = session.query(MeasureBlock).filter(
            MeasureBlock.measure_type == measure_type).filter(
            MeasureBlock.s3_key.is_(None)).order_by(
            MeasureBlock.end_id).limit(limit)

        c = 0
        for block in query:
            write_block_to_s3.apply_async(
                args=[block.id],
                kwargs={'batch': batch, 'cleanup_zip': cleanup_zip},
                countdown=c)
            c += countdown


@celery.task(base=DatabaseTask, bind=True)
def write_block_to_s3(self, block_id, batch=10000, cleanup_zip=True):

    with self.db_session() as session:
        block = session.query(MeasureBlock).filter(
            MeasureBlock.id == block_id).first()

        measure_type = block.measure_type
        measure_cls = MEASURE_TYPE_META[measure_type]['class']
        csv_name = MEASURE_TYPE_META[measure_type]['csv_name']
        name = MEASURE_TYPE_CODE_INVERSE[measure_type]

        start_id = block.start_id
        end_id = block.end_id

        rset = session.execute("select version_num from alembic_version")
        alembic_rev = rset.first()[0]

        s3_backend = S3Backend(
            self.app.s3_settings['backup_bucket'],
            self.heka_client)

        utcnow = util.utcnow()
        s3_key = '%s/%s_%d_%d.zip' % (utcnow.strftime("%Y%m"),
                                      name,
                                      start_id,
                                      end_id)

        with selfdestruct_tempdir(s3_key) as (tmp_path, zip_path):
            with open(os.path.join(tmp_path,
                                   'alembic_revision.txt'), 'w') as f:
                f.write('%s\n' % alembic_rev)

            # avoid ORM session overhead
            table = measure_cls.__table__

            cm_fname = os.path.join(tmp_path, csv_name)
            with open(cm_fname, 'w') as f:
                csv_out = csv.writer(f, dialect='excel')
                columns = table.c.keys()
                csv_out.writerow(columns)
                for this_start in range(start_id,
                                        end_id,
                                        batch):
                    this_end = min(this_start + batch, end_id)

                    query = table.select().where(
                        table.c.id >= this_start).where(
                        table.c.id < this_end)

                    rproxy = session.execute(query)
                    csv_out.writerows(rproxy)

        archive_sha = compute_hash(zip_path)

        try:
            if not s3_backend.backup_archive(s3_key, zip_path):
                return
            self.stats_client.incr('s3.backup.%s' % name, (end_id - start_id))
        finally:
            if cleanup_zip:
                if os.path.exists(zip_path):
                    zip_dir, zip_file = os.path.split(zip_path)
                    if os.path.exists(zip_dir):
                        shutil.rmtree(zip_dir)
            else:
                self.heka_client.debug("s3.backup:%s" % zip_path)

        # only set archive_sha / s3_key if upload was successful
        block.archive_sha = archive_sha
        block.s3_key = s3_key
        session.commit()


def schedule_measure_archival(self, measure_type, limit=100, batch=1000000):
    blocks = []
    measure_meta = MEASURE_TYPE_META[measure_type]
    measure_cls = measure_meta['class']
    with self.db_session() as session:
        table_min_id = 0
        table_max_id = 0

        query = session.query(measure_cls.id).order_by(
            measure_cls.id.asc())
        record = query.first()
        if record is not None:
            table_min_id = record[0]

        query = session.query(measure_cls.id).order_by(
            measure_cls.id.desc())
        record = query.first()
        if record is not None:
            table_max_id = record[0]

        if not table_max_id:
            # no data in the table
            return blocks

        query = session.query(MeasureBlock.end_id).filter(
            MeasureBlock.measure_type == measure_type).order_by(
            MeasureBlock.end_id.desc())
        record = query.first()
        if record is not None:
            min_id = record[0]
        else:
            min_id = table_min_id

        max_id = table_max_id
        if max_id - min_id < batch - 1:
            # Not enough to fill a block
            return blocks

        # We're using half-open ranges, so we need to bump the max_id
        max_id += 1

        this_max_id = min_id + batch

        i = 0
        while i < limit and (this_max_id - min_id) == batch:
            cm_blk = MeasureBlock(start_id=min_id,
                                  end_id=this_max_id,
                                  measure_type=measure_type)
            blocks.append((cm_blk.start_id, cm_blk.end_id))
            session.add(cm_blk)

            min_id = this_max_id
            this_max_id = min(batch + this_max_id, max_id)
            i += 1
        session.commit()
    return blocks


@celery.task(base=DatabaseTask, bind=True)
def schedule_cellmeasure_archival(self, limit=100, batch=1000000):
    return schedule_measure_archival(
        self, MEASURE_TYPE_CODE['cell'], limit=limit, batch=batch)


@celery.task(base=DatabaseTask, bind=True)
def schedule_wifimeasure_archival(self, limit=100, batch=1000000):
    return schedule_measure_archival(
        self, MEASURE_TYPE_CODE['wifi'], limit=limit, batch=batch)


def delete_measure_records(self,
                           measure_type,
                           limit=100,
                           days_old=7,
                           countdown=300):
    utcnow = util.utcnow()

    with self.db_session() as session:
        query = session.query(MeasureBlock).filter(
            MeasureBlock.measure_type == measure_type).filter(
            MeasureBlock.s3_key.isnot(None)).filter(
            MeasureBlock.archive_sha.isnot(None)).filter(
            MeasureBlock.archive_date.is_(None)).order_by(
            MeasureBlock.end_id.asc()).limit(limit)
        c = 0
        for block in query.all():
            # Note that 'created' is indexed for both CellMeasure
            # and WifiMeasure
            measure_cls = MEASURE_TYPE_META[measure_type]['class']
            tbl = measure_cls.__table__
            qry = session.query(func.max(tbl.c.created)).filter(
                tbl.c.id < block.end_id)
            max_created = qry.first()[0].replace(tzinfo=pytz.UTC)
            if (utcnow - max_created).days < days_old:
                # Skip this block from deletion, it's not old
                # enough
                continue

            dispatch_delete.apply_async(args=[block.id], countdown=c)
            c += countdown


@celery.task(base=DatabaseTask, bind=True)
def dispatch_delete(self, block_id):
    s3_backend = S3Backend(self.app.s3_settings['backup_bucket'],
                           self.heka_client)
    utcnow = util.utcnow()
    with self.db_session() as session:
        block = session.query(MeasureBlock).filter(
            MeasureBlock.id == block_id).first()
        measure_type = block.measure_type
        measure_cls = MEASURE_TYPE_META[measure_type]['class']
        if s3_backend.check_archive(block.archive_sha, block.s3_key):
            q = session.query(measure_cls).filter(
                measure_cls.id >= block.start_id,
                measure_cls.id < block.end_id)
            q.delete()
            block.archive_date = utcnow
            session.commit()


@celery.task(base=DatabaseTask, bind=True)
def delete_cellmeasure_records(self, limit=100, days_old=7, countdown=300):
    return delete_measure_records(
        self,
        MEASURE_TYPE_CODE['cell'],
        limit=limit,
        days_old=days_old,
        countdown=countdown)


@celery.task(base=DatabaseTask, bind=True)
def delete_wifimeasure_records(self, limit=100, days_old=7, countdown=300):
    return delete_measure_records(
        self,
        MEASURE_TYPE_CODE['wifi'],
        limit=limit,
        days_old=days_old,
        countdown=countdown)


def unthrottle_measures(session, station_model, measure_model,
                        join_measure, max_measures, batch):
    """
    Periodically recalculate the total_measures value for any 'throttled'
    station, that is, one with total_measures >= max_measures, which is
    therefore dropping additional incoming measures on the floor. This
    recalculation (potentially, temporarily) 'un-throttles' the rate, due
    to the fact that every night, a day worth of measures is backed up and
    purged from the measures table, so some new room may be made in the
    measure tables for new measures to be absorbed. Once a station's
    total_measures count gets back up to max_measures, it will be throttled
    again.

    """
    q = session.query(station_model).filter(
        station_model.total_measures > max_measures).limit(batch)

    unthrottled = 0
    for station in q.all():
        q = session.query(func.count(measure_model.id)).filter(
            *join_measure(station))
        c = q.first()
        n = int(c[0])
        assert n <= station.total_measures
        unthrottled += station.total_measures - n
        station.total_measures = n
        station.new_measures = min(station.new_measures, n)

    session.commit()
    return unthrottled


@celery.task(base=DatabaseTask, bind=True)
def wifi_unthrottle_measures(self, max_measures, batch=1000):
    try:
        with self.db_session() as session:
            join_measure = lambda u: (WifiMeasure.key == u.key, )
            n = unthrottle_measures(session=session,
                                    station_model=Wifi,
                                    measure_model=WifiMeasure,
                                    join_measure=join_measure,
                                    max_measures=max_measures,
                                    batch=batch)
            self.stats_client.incr("items.wifi_unthrottled", n)
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)


@celery.task(base=DatabaseTask, bind=True)
def cell_unthrottle_measures(self, max_measures, batch=100):
    try:
        with self.db_session() as session:
            join_measure = lambda u: join_cellkey(CellMeasure, u)
            n = unthrottle_measures(session=session,
                                    station_model=Cell,
                                    measure_model=CellMeasure,
                                    join_measure=join_measure,
                                    max_measures=max_measures,
                                    batch=batch)
            self.stats_client.incr("items.cell_unthrottled", n)
    except Exception as exc:  # pragma: no cover
        self.heka_client.raven('error')
        raise self.retry(exc=exc)
