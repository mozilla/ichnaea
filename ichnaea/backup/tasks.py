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
def write_cellmeasure_s3_backups(self, cleanup_zip=True):
    measure_type = MEASURE_TYPE['cell']
    zip_prefix = 'CellMeasure'
    csv_name = 'cell_measure.csv'
    measure_cls = CellMeasure
    return write_measure_s3_backups(self,
                                    measure_type,
                                    zip_prefix,
                                    csv_name,
                                    measure_cls,
                                    cleanup_zip)


@celery.task(base=DatabaseTask, bind=True)
def write_wifimeasure_s3_backups(self, cleanup_zip=True):
    measure_type = MEASURE_TYPE['wifi']
    zip_prefix = 'WifiMeasure'
    csv_name = 'wifi_measure.csv'
    measure_cls = WifiMeasure
    return write_measure_s3_backups(self,
                                    measure_type,
                                    zip_prefix,
                                    csv_name,
                                    measure_cls,
                                    cleanup_zip)


def write_measure_s3_backups(self, measure_type,
                             zip_prefix, csv_name,
                             measure_cls, cleanup_zip):
    """
    Iterate over each of the measure block records that aren't
    backed up yet and back them up.

    Assume that this is running in a single task.
    """

    zips = []
    utcnow = datetime.datetime.utcnow()
    s3_backend = S3Backend(
        self.app.s3_settings['backup_bucket'],
        self.app.s3_settings['backup_prefix'],
        self.heka_client)

    with self.db_session() as session:
        query = session.query(MeasureBlock).filter(
            MeasureBlock.measure_type == measure_type).filter(
            MeasureBlock.archive_date.is_(None)).order_by(
            MeasureBlock.end_id)
        for cmb in query.all():
            cmb.s3_key = '%s/%s_%d_%d.zip' % (
                utcnow.strftime("%Y%m"),
                zip_prefix,
                cmb.start_id,
                cmb.end_id)

            with selfdestruct_tempdir(cmb.s3_key) as (tmp_path, zip_path):
                rset = session.execute("select * from alembic_version")
                rev = rset.first()[0]
                with open(os.path.join(tmp_path,
                                       'alembic_revision.txt'), 'w') as f:
                    f.write('%s\n' % rev)

                cm_fname = os.path.join(tmp_path, csv_name)

                cm_query = session.query(measure_cls).filter(
                    measure_cls.id >= cmb.start_id).filter(
                    measure_cls.id < cmb.end_id)

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

            cmb.archive_sha = compute_hash(zip_path)

            try:
                if not s3_backend.backup_archive(cmb.s3_key, zip_path):
                    continue
                self.heka_client.incr('s3.backup.%s' % measure_type,
                                      (cmb.end_id - cmb.start_id))
            finally:
                if cleanup_zip:
                    if os.path.exists(zip_path):
                        zip_dir, zip_file = os.path.split(zip_path)
                        if os.path.exists(zip_dir):
                            shutil.rmtree(zip_dir)
                else:
                    zips.append(zip_path)

            session.add(cmb)
            session.commit()
    return zips


def schedule_measure_archival(self, measure_type, measure_cls, batch=100):
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

        while (this_max_id - min_id) == batch:
            cm_blk = MeasureBlock(start_id=min_id,
                                  end_id=this_max_id,
                                  measure_type=measure_type)
            blocks.append((cm_blk.start_id, cm_blk.end_id))
            session.add(cm_blk)

            min_id = this_max_id
            this_max_id = min(batch + this_max_id, max_id)
        session.commit()
    return blocks


@celery.task(base=DatabaseTask, bind=True)
def schedule_cellmeasure_archival(self, batch=100):
    return schedule_measure_archival(
        self, MEASURE_TYPE['cell'], CellMeasure, batch)


@celery.task(base=DatabaseTask, bind=True)
def schedule_wifimeasure_archival(self, batch=100):
    return schedule_measure_archival(
        self, MEASURE_TYPE['wifi'], WifiMeasure, batch)


def delete_measure_records(self, measure_type, measure_cls, cleanup_zip):
    s3_backend = S3Backend(
        self.app.s3_settings['backup_bucket'],
        self.app.s3_settings['backup_prefix'],
        self.heka_client)

    with self.db_session() as session:
        query = session.query(MeasureBlock).filter(
            MeasureBlock.measure_type == measure_type).filter(
            MeasureBlock.s3_key.isnot(None)).filter(
            MeasureBlock.archive_date.isnot(None))
        for cmb in query.all():
            expected_sha = cmb.archive_sha
            if s3_backend.check_archive(expected_sha, cmb.s3_key):
                q = session.query(measure_cls).filter(
                    measure_cls.id >= cmb.start_id,
                    measure_cls.id <= cmb.end_id)
                q.delete()
                session.commit()


@celery.task(base=DatabaseTask, bind=True)
def delete_cellmeasure_records(self, cleanup_zip=True):
    return delete_measure_records(
        self, MEASURE_TYPE['cell'], CellMeasure, cleanup_zip)


@celery.task(base=DatabaseTask, bind=True)
def delete_wifimeasure_records(self, cleanup_zip=True):
    return delete_measure_records(
        self, MEASURE_TYPE['wifi'], WifiMeasure, cleanup_zip)
