from datetime import timedelta

import pytz
from sqlalchemy import func

from ichnaea.async.app import celery_app
from ichnaea.async.task import DatabaseTask
from ichnaea.models import (
    OBSERVATION_TYPE_META,
    ObservationBlock,
    ObservationType,
)
from ichnaea import util


@celery_app.task(base=DatabaseTask, bind=True)
def write_cellmeasure_s3_backups(self,
                                 limit=100,
                                 batch=10000,
                                 countdown=300,
                                 cleanup_zip=True):
    return write_observation_s3_backups(self,
                                        ObservationType.cell,
                                        limit=limit,
                                        batch=batch,
                                        countdown=countdown,
                                        cleanup_zip=cleanup_zip)


@celery_app.task(base=DatabaseTask, bind=True)
def write_wifimeasure_s3_backups(self,
                                 limit=100,
                                 batch=10000,
                                 countdown=300,
                                 cleanup_zip=True):
    return write_observation_s3_backups(self,
                                        ObservationType.wifi,
                                        limit=limit,
                                        batch=batch,
                                        countdown=countdown,
                                        cleanup_zip=cleanup_zip)


def write_observation_s3_backups(self,
                                 observation_type,
                                 limit=100,
                                 batch=10000,
                                 countdown=300,
                                 cleanup_zip=True):
    """
    Iterate over each of the observation block records that aren't
    backed up yet and back them up.
    """
    with self.db_session() as session:
        query = session.query(ObservationBlock).filter(
            ObservationBlock.measure_type == observation_type).filter(
            ObservationBlock.s3_key.is_(None)).order_by(
            ObservationBlock.end_id).limit(limit)

        for block in query:
            # always set archive flags to successful
            block.archive_sha = '20bytes_mean_success'
            block.s3_key = 'skipped'
        session.commit()


@celery_app.task(base=DatabaseTask, bind=True)
def write_block_to_s3(self, block_id,
                      batch=10000, cleanup_zip=True):  # pragma: no cover
    pass


def schedule_observation_archival(self, observation_type,
                                  limit=100, batch=1000000):
    blocks = []
    obs_meta = OBSERVATION_TYPE_META[observation_type]
    obs_cls = obs_meta['class']
    with self.db_session() as session:
        table_min_id = 0
        table_max_id = 0

        query = session.query(obs_cls.id).order_by(
            obs_cls.id.asc())
        record = query.first()
        if record is not None:
            table_min_id = record[0]

        query = session.query(obs_cls.id).order_by(
            obs_cls.id.desc())
        record = query.first()
        if record is not None:
            table_max_id = record[0]

        if not table_max_id:
            # no data in the table
            return blocks

        query = session.query(ObservationBlock.end_id).filter(
            ObservationBlock.measure_type == observation_type).order_by(
            ObservationBlock.end_id.desc())
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
            cm_blk = ObservationBlock(start_id=min_id,
                                      end_id=this_max_id,
                                      measure_type=observation_type)
            blocks.append((cm_blk.start_id, cm_blk.end_id))
            session.add(cm_blk)

            min_id = this_max_id
            this_max_id = min(batch + this_max_id, max_id)
            i += 1
        session.commit()
    return blocks


@celery_app.task(base=DatabaseTask, bind=True)
def schedule_cellmeasure_archival(self, limit=100, batch=1000000):
    return schedule_observation_archival(
        self, ObservationType.cell, limit=limit, batch=batch)


@celery_app.task(base=DatabaseTask, bind=True)
def schedule_wifimeasure_archival(self, limit=100, batch=1000000):
    return schedule_observation_archival(
        self, ObservationType.wifi, limit=limit, batch=batch)


def delete_observation_records(self,
                               observation_type,
                               limit=100,
                               days_old=7,
                               countdown=300,
                               batch=10000):
    # days_old = 1 means do not delete data from the current day
    today = util.utcnow().date()
    min_age = today - timedelta(days_old)

    with self.db_session() as session:
        query = session.query(ObservationBlock).filter(
            ObservationBlock.measure_type == observation_type).filter(
            ObservationBlock.s3_key.isnot(None)).filter(
            ObservationBlock.archive_sha.isnot(None)).filter(
            ObservationBlock.archive_date.is_(None)).order_by(
            ObservationBlock.end_id.asc()).limit(limit)
        c = 0
        for block in query.all():
            # Note that 'created' is indexed for both CellObservation
            # and WifiObservation
            obs_cls = OBSERVATION_TYPE_META[observation_type]['class']
            tbl = obs_cls.__table__
            qry = session.query(func.max(tbl.c.created)).filter(
                tbl.c.id < block.end_id)
            max_created = qry.first()[0].replace(tzinfo=pytz.UTC).date()
            if min_age < max_created:
                # Skip this block from deletion, it's not old
                # enough
                continue

            verified_delete.apply_async(
                args=[block.id],
                kwargs={'batch': batch},
                countdown=c)
            c += countdown


@celery_app.task(base=DatabaseTask, bind=True)
def dispatch_delete(self, block_id, batch=10000):  # pragma: no cover
    pass


@celery_app.task(base=DatabaseTask, bind=True)
def verified_delete(self, block_id, batch=10000):
    utcnow = util.utcnow()
    with self.db_session() as session:
        block = session.query(ObservationBlock).filter(
            ObservationBlock.id == block_id).first()
        observation_type = block.measure_type
        obs_cls = OBSERVATION_TYPE_META[observation_type]['class']

        for start in range(block.start_id, block.end_id, batch):
            end = min(block.end_id, start + batch)
            q = session.query(obs_cls).filter(
                obs_cls.id >= start,
                obs_cls.id < end)
            q.delete()
            session.flush()
        block.archive_date = utcnow
        session.commit()


@celery_app.task(base=DatabaseTask, bind=True)
def delete_cellmeasure_records(self, limit=100, days_old=7,
                               countdown=300, batch=10000):
    return delete_observation_records(
        self,
        ObservationType.cell,
        limit=limit,
        days_old=days_old,
        countdown=countdown,
        batch=batch)


@celery_app.task(base=DatabaseTask, bind=True)
def delete_wifimeasure_records(self, limit=100, days_old=7,
                               countdown=300, batch=10000):
    return delete_observation_records(
        self,
        ObservationType.wifi,
        limit=limit,
        days_old=days_old,
        countdown=countdown,
        batch=batch)
