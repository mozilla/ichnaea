from contextlib import contextmanager
import datetime
from datetime import timedelta
import hashlib
from zipfile import ZipFile

import boto
from mock import MagicMock, patch
import pytz

from ichnaea.backup.s3 import S3Backend
from ichnaea.backup.tasks import (
    delete_cellmeasure_records,
    delete_wifimeasure_records,
    schedule_cellmeasure_archival,
    schedule_wifimeasure_archival,
    write_cellmeasure_s3_backups,
    write_wifimeasure_s3_backups,
    cell_unthrottle_measures,
    wifi_unthrottle_measures,
)
from ichnaea.models import (
    Cell,
    CellObservation,
    ObservationBlock,
    ObservationType,
    Wifi,
    WifiObservation,
)
from ichnaea.tests.base import CeleryTestCase
from ichnaea.tests.factories import (
    CellFactory,
    CellObservationFactory,
    ObservationBlockFactory,
    WifiFactory,
    WifiObservationFactory,
)
from ichnaea import util


@contextmanager
def mock_s3():
    mock_conn = MagicMock()
    mock_key = MagicMock()
    with patch.object(boto, 'connect_s3', mock_conn):
        with patch('boto.s3.key.Key', lambda _: mock_key):
            yield mock_key


class TestBackup(CeleryTestCase):

    def test_backup(self):
        with mock_s3() as mock_key:
            s3 = S3Backend('localhost.bucket', self.heka_client)
            s3.backup_archive('some_key', '/tmp/not_a_real_file.zip')
            self.assertEquals(mock_key.key, 'backups/some_key')
            method = mock_key.set_contents_from_filename
            self.assertEquals(method.call_args[0][0],
                              '/tmp/not_a_real_file.zip')


class TestObservationsDump(CeleryTestCase):

    def setUp(self):
        CeleryTestCase.setUp(self)
        self.really_old = datetime.datetime(1980, 1, 1).replace(
            tzinfo=pytz.UTC)

    def test_schedule_cell_observations(self):
        blocks = schedule_cellmeasure_archival.delay(batch=1).get()
        self.assertEquals(len(blocks), 0)

        observations = []
        obs_factory = CellObservationFactory.create
        for i in range(20):
            observations.append(obs_factory(created=self.really_old))
        self.session.flush()
        start_id = observations[0].id

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
        observations = []
        obs_factory = WifiObservationFactory.create
        for i in range(batch_size * 2):
            observations.append(obs_factory(created=self.really_old))
        self.session.flush()
        start_id = observations[0].id

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
        observations = []
        obs_factory = CellObservationFactory.create
        for i in range(batch_size):
            observations.append(obs_factory(created=self.really_old))
        self.session.flush()
        start_id = observations[0].id

        blocks = schedule_cellmeasure_archival.delay(batch=batch_size).get()
        self.assertEquals(len(blocks), 1)
        block = blocks[0]
        self.assertEquals(block, (start_id, start_id + batch_size))

        with mock_s3():
            with patch.object(S3Backend,
                              'backup_archive', lambda x, y, z: True):
                write_cellmeasure_s3_backups.delay(cleanup_zip=False).get()

                msgs = self.heka_client.stream.msgs
                info_msgs = [m for m in msgs if m.type == 'oldstyle']
                self.assertEquals(1, len(info_msgs))
                info = info_msgs[0]
                fname = info.payload.split(":")[-1]

                myzip = ZipFile(fname)
                try:
                    contents = set(myzip.namelist())
                    expected_contents = set(['alembic_revision.txt',
                                             'cell_measure.csv'])
                    self.assertEquals(expected_contents, contents)
                finally:
                    myzip.close()

        blocks = self.session.query(ObservationBlock).all()

        self.assertEquals(len(blocks), 1)
        block = blocks[0]

        actual_sha = hashlib.sha1()
        actual_sha.update(open(fname, 'rb').read())
        self.assertEquals(block.archive_sha, actual_sha.digest())
        self.assertTrue(block.s3_key is not None)
        self.assertTrue('/cell_' in block.s3_key)
        self.assertTrue(block.archive_date is None)

    def test_backup_wifi_to_s3(self):
        batch_size = 10
        observations = []
        obs_factory = WifiObservationFactory.create
        for i in range(batch_size):
            observations.append(obs_factory(created=self.really_old))
        self.session.flush()
        start_id = observations[0].id

        blocks = schedule_wifimeasure_archival.delay(batch=batch_size).get()
        self.assertEquals(len(blocks), 1)
        block = blocks[0]
        self.assertEquals(block, (start_id, start_id + batch_size))

        with mock_s3():
            with patch.object(S3Backend,
                              'backup_archive', lambda x, y, z: True):
                write_wifimeasure_s3_backups.delay(cleanup_zip=False).get()

                msgs = self.heka_client.stream.msgs
                info_msgs = [m for m in msgs if m.type == 'oldstyle']
                self.assertEquals(1, len(info_msgs))
                info = info_msgs[0]
                fname = info.payload.split(":")[-1]

                myzip = ZipFile(fname)
                try:
                    contents = set(myzip.namelist())
                    expected_contents = set(['alembic_revision.txt',
                                             'wifi_measure.csv'])
                    self.assertEquals(expected_contents, contents)
                finally:
                    myzip.close()

        blocks = self.session.query(ObservationBlock).all()

        self.assertEquals(len(blocks), 1)
        block = blocks[0]

        actual_sha = hashlib.sha1()
        actual_sha.update(open(fname, 'rb').read())
        self.assertEquals(block.archive_sha, actual_sha.digest())
        self.assertTrue(block.s3_key is not None)
        self.assertTrue('/wifi_' in block.s3_key)
        self.assertTrue(block.archive_date is None)

    def test_delete_cell_observations(self):
        obs_factory = CellObservationFactory.create
        observations = []
        for i in range(50):
            observations.append(obs_factory(created=self.really_old))
        self.session.flush()

        start_id = observations[0].id + 20
        block_factory = ObservationBlockFactory.create
        block = block_factory(
            measure_type=ObservationType.cell,
            start_id=start_id, end_id=start_id + 20, archive_date=None)
        self.session.commit()

        with patch.object(S3Backend, 'check_archive', lambda x, y, z: True):
            delete_cellmeasure_records.delay(batch=3).get()

        self.assertEquals(self.session.query(CellObservation).count(), 30)
        self.assertTrue(block.archive_date is not None)

    def test_delete_wifi_observations(self):
        obs_factory = WifiObservationFactory.create
        observations = []
        for i in range(50):
            observations.append(obs_factory(created=self.really_old))
        self.session.flush()

        start_id = observations[0].id + 20
        block_factory = ObservationBlockFactory.create
        block = block_factory(
            measure_type=ObservationType.wifi,
            start_id=start_id, end_id=start_id + 20, archive_date=None)
        self.session.commit()

        with patch.object(S3Backend, 'check_archive', lambda x, y, z: True):
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

        block_factory = ObservationBlockFactory.create
        for i in range(100, 150, 10):
            block_factory(
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
            with patch.object(S3Backend,
                              'check_archive',
                              lambda x, y, z: True):
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

    def test_unthrottle_cell_observations(self):
        cell_factory = CellFactory.create
        obs_factory = CellObservationFactory.create
        observations = []
        for i in range(100, 150):
            observations.append(obs_factory(created=self.really_old, cid=i))
            cell_factory(total_measures=11000, cid=i)
        self.session.flush()

        start_id = observations[0].id + 20
        block_factory = ObservationBlockFactory.create
        block_factory(
            measure_type=ObservationType.cell,
            start_id=start_id, end_id=start_id + 20, archive_date=None)
        self.session.commit()

        with patch.object(S3Backend, 'check_archive', lambda x, y, z: True):
            delete_cellmeasure_records.delay(batch=3).get()

        cell_unthrottle_measures.delay(10000, 1000).get()

        cells = self.session.query(Cell).all()
        self.assertEquals(len(cells), 50)
        for cell in cells:
            if 120 <= cell.cid and cell.cid < 140:
                self.assertEquals(cell.total_measures, 0)
            else:
                self.assertEquals(cell.total_measures, 1)

        self.check_stats(counter=['items.cell_unthrottled'])

    def test_unthrottle_wifi_observations(self):
        wifi_factory = WifiFactory.create
        obs_factory = WifiObservationFactory.create
        observations = []
        to_key = lambda num: "a01234567{num:03d}".format(num=num)
        for i in range(100, 150):
            observations.append(
                obs_factory(created=self.really_old, key=to_key(i)))
            wifi_factory(total_measures=11000, key=to_key(i))
        self.session.flush()

        start_id = observations[0].id + 20
        block_factory = ObservationBlockFactory.create
        block_factory(
            measure_type=ObservationType.wifi,
            start_id=start_id, end_id=start_id + 20, archive_date=None)
        self.session.commit()

        with patch.object(S3Backend, 'check_archive', lambda x, y, z: True):
            delete_wifimeasure_records.delay(batch=7).get()

        wifi_unthrottle_measures.delay(10000, 1000).get()

        wifis = self.session.query(Wifi).all()
        self.assertEquals(len(wifis), 50)
        for wifi in wifis:
            if 120 <= int(wifi.key[-3:]) and int(wifi.key[-3:]) < 140:
                self.assertEquals(wifi.total_measures, 0)
            else:
                self.assertEquals(wifi.total_measures, 1)

        self.check_stats(counter=['items.wifi_unthrottled'])
