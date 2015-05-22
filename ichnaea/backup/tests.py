import datetime
from datetime import timedelta

import pytz

from ichnaea.backup.tasks import (
    delete_cellmeasure_records,
    delete_wifimeasure_records,
    schedule_cellmeasure_archival,
    schedule_wifimeasure_archival,
    write_cellmeasure_s3_backups,
    write_wifimeasure_s3_backups,
)
from ichnaea.models import (
    CellObservation,
    ObservationBlock,
    ObservationType,
    WifiObservation,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    CellObservationFactory,
    ObservationBlockFactory,
    WifiObservationFactory,
)
from ichnaea import util


class TestObservationsDump(CeleryTestCase):

    def setUp(self):
        super(TestObservationsDump, self).setUp()
        self.old = datetime.datetime(1980, 1, 1).replace(
            tzinfo=pytz.UTC)

    def test_schedule_cell_observations(self):
        blocks = schedule_cellmeasure_archival.delay(batch=1).get()
        self.assertEquals(len(blocks), 0)

        obs = CellObservationFactory.create_batch(20, created=self.old)
        self.session.flush()
        start_id = obs[0].id

        blocks = schedule_cellmeasure_archival.delay(batch=15).get()
        self.assertEquals(len(blocks), 1)
        block = blocks[0]
        self.assertEquals(block, (start_id, start_id + 15))

        blocks = schedule_cellmeasure_archival.delay(batch=6).get()
        self.assertEquals(len(blocks), 0)

        blocks = schedule_cellmeasure_archival.delay(batch=5).get()
        self.assertEquals(len(blocks), 1)
        block = blocks[0]
        self.assertEquals(block, (start_id + 15, start_id + 20))

        blocks = schedule_cellmeasure_archival.delay(batch=1).get()
        self.assertEquals(len(blocks), 0)

    def test_schedule_wifi_observations(self):
        blocks = schedule_wifimeasure_archival.delay(batch=1).get()
        self.assertEquals(len(blocks), 0)

        batch_size = 10
        obs = WifiObservationFactory.create_batch(
            batch_size * 2, created=self.old)
        self.session.flush()
        start_id = obs[0].id

        blocks = schedule_wifimeasure_archival.delay(batch=batch_size).get()
        self.assertEquals(len(blocks), 2)
        block = blocks[0]
        self.assertEquals(block,
                          (start_id, start_id + batch_size))

        block = blocks[1]
        self.assertEquals(block,
                          (start_id + batch_size, start_id + 2 * batch_size))

        blocks = schedule_wifimeasure_archival.delay(batch=batch_size).get()
        self.assertEquals(len(blocks), 0)

    def test_backup_cell_to_s3(self):
        batch_size = 10
        obs = CellObservationFactory.create_batch(batch_size, created=self.old)
        self.session.flush()
        start_id = obs[0].id

        blocks = schedule_cellmeasure_archival.delay(batch=batch_size).get()
        self.assertEquals(len(blocks), 1)
        block = blocks[0]
        self.assertEquals(block, (start_id, start_id + batch_size))

        write_cellmeasure_s3_backups.delay(cleanup_zip=False).get()

        blocks = self.session.query(ObservationBlock).all()
        self.assertEquals(len(blocks), 1)
        block = blocks[0]

        self.assertEqual(block.archive_sha, '20bytes_mean_success')
        self.assertEqual(block.s3_key, 'skipped')
        self.assertTrue(block.archive_date is None)

    def test_backup_wifi_to_s3(self):
        batch_size = 10
        obs = WifiObservationFactory.create_batch(batch_size, created=self.old)
        self.session.flush()
        start_id = obs[0].id

        blocks = schedule_wifimeasure_archival.delay(batch=batch_size).get()
        self.assertEquals(len(blocks), 1)
        block = blocks[0]
        self.assertEquals(block, (start_id, start_id + batch_size))

        write_wifimeasure_s3_backups.delay(cleanup_zip=False).get()

        blocks = self.session.query(ObservationBlock).all()
        self.assertEquals(len(blocks), 1)
        block = blocks[0]

        self.assertEqual(block.archive_sha, '20bytes_mean_success')
        self.assertEqual(block.s3_key, 'skipped')
        self.assertTrue(block.archive_date is None)

    def test_delete_cell_observations(self):
        obs = CellObservationFactory.create_batch(50, created=self.old)
        self.session.flush()

        start_id = obs[0].id + 20
        block = ObservationBlockFactory(
            measure_type=ObservationType.cell,
            start_id=start_id, end_id=start_id + 20, archive_date=None)
        self.session.commit()

        delete_cellmeasure_records.delay(batch=3).get()

        self.assertEquals(self.session.query(CellObservation).count(), 30)
        self.assertTrue(block.archive_date is not None)

    def test_delete_wifi_observations(self):
        obs = WifiObservationFactory.create_batch(50, created=self.old)
        self.session.flush()

        start_id = obs[0].id + 20
        block = ObservationBlockFactory(
            measure_type=ObservationType.wifi,
            start_id=start_id, end_id=start_id + 20, archive_date=None)
        self.session.commit()

        delete_wifimeasure_records.delay(batch=7).get()

        self.assertEquals(self.session.query(WifiObservation).count(), 30)
        self.assertTrue(block.archive_date is not None)

    def test_skip_delete_new_blocks(self):
        now = util.utcnow()
        today_0000 = now.replace(hour=0, minute=0, second=0, tzinfo=pytz.UTC)
        yesterday_0000 = today_0000 - timedelta(days=1)
        yesterday_2359 = today_0000 - timedelta(seconds=1)
        old = now - timedelta(days=5)
        session = self.session

        for i in range(100, 150, 10):
            ObservationBlockFactory(
                measure_type=ObservationType.cell,
                start_id=i, end_id=i + 10, archive_date=None)

        observations = []
        for i in range(100, 110):
            observations.append(CellObservation(id=i, created=old))
        for i in range(110, 120):
            observations.append(CellObservation(id=i, created=yesterday_0000))
        for i in range(120, 130):
            observations.append(CellObservation(id=i, created=yesterday_2359))
        for i in range(130, 140):
            observations.append(CellObservation(id=i, created=today_0000))
        for i in range(140, 150):
            observations.append(CellObservation(id=i, created=now))

        session.add_all(observations)
        session.commit()

        def _archived_blocks():
            blocks = session.query(ObservationBlock).all()
            return len([b for b in blocks if b.archive_date is not None])

        def _delete(days=7):
            delete_cellmeasure_records.delay(days_old=days).get()
            session.commit()

        _delete(days=7)
        self.assertEquals(session.query(CellObservation).count(), 50)
        self.assertEqual(_archived_blocks(), 0)

        _delete(days=2)
        self.assertEquals(session.query(CellObservation).count(), 40)
        self.assertEqual(_archived_blocks(), 1)

        _delete(days=1)
        self.assertEquals(session.query(CellObservation).count(), 20)
        self.assertEqual(_archived_blocks(), 3)

        _delete(days=0)
        self.assertEquals(session.query(CellObservation).count(), 0)
        self.assertEqual(_archived_blocks(), 5)
