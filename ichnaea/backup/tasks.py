import csv
from contextlib import contextmanager
import datetime
import os
import shutil
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from ichnaea.backup.s3 import S3Backend, compute_hash
from ichnaea.models import (
    CellMeasure,
    MEASURE_TYPE,
    MeasureBlock,
    WifiMeasure,
)
from ichnaea.tasks import DatabaseTask
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
def write_cellmeasure_s3_backups(self, limit=100, cleanup_zip=True):
    measure_type = MEASURE_TYPE['cell']
    zip_prefix = 'CellMeasure'
    csv_name = 'cell_measure.csv'
    measure_cls = CellMeasure
    return write_measure_s3_backups(self,
                                    measure_type,
                                    zip_prefix,
                                    csv_name,
                                    measure_cls,
                                    limit=limit,
                                    cleanup_zip=cleanup_zip)


@celery.task(base=DatabaseTask, bind=True)
def write_wifimeasure_s3_backups(self, limit=100, cleanup_zip=True):
    measure_type = MEASURE_TYPE['wifi']
    zip_prefix = 'WifiMeasure'
    csv_name = 'wifi_measure.csv'
    measure_cls = WifiMeasure
    return write_measure_s3_backups(self,
                                    measure_type,
                                    zip_prefix,
                                    csv_name,
                                    measure_cls,
                                    limit=limit,
                                    cleanup_zip=cleanup_zip)


def write_measure_s3_backups(self, measure_type,
                             zip_prefix, csv_name,
                             measure_cls, limit=100, cleanup_zip=True):
    """
    Iterate over each of the measure block records that aren't
    backed up yet and back them up.

    Assume that this is running in a single task.
    """
    with self.db_session() as session:

        query = session.query(MeasureBlock).filter(
            MeasureBlock.measure_type == measure_type).filter(
            MeasureBlock.s3_key.is_(None)).order_by(
            MeasureBlock.end_id).limit(limit)

        for block in query:
            # TODO: change this to invoke .delay(*args) instead
            do_write_measure_s3_backups.delay(measure_type,
                                              zip_prefix,
                                              csv_name,
                                              measure_cls.__name__,
                                              limit,
                                              cleanup_zip,
                                              block.id,
                                              block.start_id,
                                              block.end_id,)


@celery.task(base=DatabaseTask, bind=True)
def do_write_measure_s3_backups(self,
                                measure_type,
                                zip_prefix,
                                csv_name,
                                measure_cls_name,
                                limit,
                                cleanup_zip,
                                block_id,
                                start_id,  # TODO: get rid of start/end_id
                                end_id):

    from ichnaea import models
    measure_cls = getattr(models, measure_cls_name)

    with self.db_session() as session:
        rset = session.execute("select version_num from alembic_version")
        alembic_rev = rset.first()[0]

        s3_backend = S3Backend(
            self.app.s3_settings['backup_bucket'],
            self.app.s3_settings['backup_prefix'],
            self.heka_client)

        chunk_size = self.app.s3_settings['backup_chunksize']

        utcnow = datetime.datetime.utcnow()
        s3_key = '%s/%s_%d_%d.zip' % (utcnow.strftime("%Y%m"),
                                      zip_prefix,
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
                for this_start in range(start_id,
                                        end_id,
                                        chunk_size):
                    this_end = min(this_start+chunk_size, end_id)

                    query = table.select().where(
                        table.c.id >= this_start).where(
                        table.c.id < this_end)

                    if this_start == start_id:
                        columns = table.c.keys()
                        csv_out.writerow(columns)

                    rproxy = session.execute(query)
                    csv_out.writerows(rproxy)

        archive_sha = compute_hash(zip_path)

        try:
            if not s3_backend.backup_archive(s3_key, zip_path):
                return
            self.heka_client.incr('s3.backup.%s' % measure_type,
                                  (end_id - start_id))
        finally:
            if cleanup_zip:
                if os.path.exists(zip_path):
                    zip_dir, zip_file = os.path.split(zip_path)
                    if os.path.exists(zip_dir):
                        shutil.rmtree(zip_dir)
            else:
                self.heka_client.debug("s3.backup:%s" % zip_path)

        # only set archive_sha / s3_key if upload was successful
        block = session.query(MeasureBlock).filter(
            MeasureBlock.id == block_id).first()
        block.archive_sha = archive_sha
        block.s3_key = s3_key
        session.commit()


def schedule_measure_archival(self, measure_type, measure_cls,
                              batch=100, limit=100):
    blocks = []
    with self.db_session() as session:
        query = session.query(MeasureBlock.end_id).filter(
            MeasureBlock.measure_type == measure_type).order_by(
            MeasureBlock.end_id.desc())
        record = query.first()
        if record is not None:
            min_id = record[0]
        else:
            query = session.query(measure_cls.id).order_by(
                measure_cls.id.asc())
            record = query.first()
            if record is not None:
                min_id = record[0]
            else:
                # no data in the table
                return blocks

        query = session.query(measure_cls.id).order_by(
            measure_cls.id.desc())
        record = query.first()
        if record is None:
            # no data in the table
            return blocks

        max_id = record[0]
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
def schedule_cellmeasure_archival(self, batch=100, limit=100):
    return schedule_measure_archival(
        self, MEASURE_TYPE['cell'], CellMeasure, batch, limit)


@celery.task(base=DatabaseTask, bind=True)
def schedule_wifimeasure_archival(self, batch=100, limit=100):
    return schedule_measure_archival(
        self, MEASURE_TYPE['wifi'], WifiMeasure, batch, limit)


def delete_measure_records(self, measure_type, measure_cls, limit=100):
    s3_backend = S3Backend(
        self.app.s3_settings['backup_bucket'],
        self.app.s3_settings['backup_prefix'],
        self.heka_client)
    utcnow = datetime.datetime.utcnow()

    with self.db_session() as session:
        query = session.query(MeasureBlock).filter(
            MeasureBlock.measure_type == measure_type).filter(
            MeasureBlock.s3_key.isnot(None)).filter(
            MeasureBlock.archive_sha.isnot(None)).filter(
            MeasureBlock.archive_date.is_(None)).order_by(
            MeasureBlock.end_id.asc()).limit(limit)
        for block in query.all():
            expected_sha = block.archive_sha
            if s3_backend.check_archive(expected_sha, block.s3_key):
                q = session.query(measure_cls).filter(
                    measure_cls.id >= block.start_id,
                    measure_cls.id <= block.end_id)
                q.delete()
                block.archive_date = utcnow
                session.commit()


@celery.task(base=DatabaseTask, bind=True)
def delete_cellmeasure_records(self, limit=100):
    return delete_measure_records(
        self, MEASURE_TYPE['cell'], CellMeasure, limit=limit)


@celery.task(base=DatabaseTask, bind=True)
def delete_wifimeasure_records(self, limit=100):
    return delete_measure_records(
        self, MEASURE_TYPE['wifi'], WifiMeasure, limit=limit)
