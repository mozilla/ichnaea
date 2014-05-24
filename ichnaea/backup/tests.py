import boto
from contextlib import contextmanager
import datetime
import hashlib
from mock import (
    MagicMock,
    patch,
)
from zipfile import ZipFile

from ichnaea.backup.s3 import S3Backend
from ichnaea.backup.tasks import (
    delete_cellmeasure_records,
    delete_wifimeasure_records,
    schedule_cellmeasure_archival,
    schedule_wifimeasure_archival,
    write_cellmeasure_s3_backups,
    write_wifimeasure_s3_backups,
)
from ichnaea.models import (
    CellMeasure,
    MeasureBlock,
    MEASURE_TYPE,
    WifiMeasure,
)
from ichnaea.tests.base import CeleryTestCase


@contextmanager
def mock_s3():
    mock_conn = MagicMock()
    mock_key = MagicMock()
    with patch.object(boto, 'connect_s3', mock_conn):
        with patch('boto.s3.key.Key', lambda _: mock_key):
            yield mock_key


class TestBackup(CeleryTestCase):

    def test_backup(self):
        prefix = 'backups/tests'
        with mock_s3() as mock_key:
            s3 = S3Backend('localhost.bucket', prefix, self.heka_client)
            s3.backup_archive('some_key', '/tmp/not_a_real_file.zip')
            self.assertEquals(mock_key.key, '/'.join([prefix, 'some_key']))
            method = mock_key.set_contents_from_filename
            self.assertEquals(method.call_args[0][0],
                              '/tmp/not_a_real_file.zip')


class TestMeasurementsDump(CeleryTestCase):

    def test_schedule_cell_measures(self):
        session = self.db_master_session
        measures = []
        for i in range(20):
            measures.append(CellMeasure())
        session.add_all(measures)
        session.flush()
        start_id = measures[0].id

        blocks = schedule_cellmeasure_archival(batch=15)
        self.assertEquals(len(blocks), 1)
        block = blocks[0]
        self.assertEquals(block, (start_id, start_id + 15))

        blocks = schedule_cellmeasure_archival(batch=6)
        self.assertEquals(len(blocks), 0)

        blocks = schedule_cellmeasure_archival(batch=5)
        self.assertEquals(len(blocks), 1)
        block = blocks[0]
        self.assertEquals(block, (start_id + 15, start_id + 20))

        blocks = schedule_cellmeasure_archival(batch=1)
        self.assertEquals(len(blocks), 0)

    def test_schedule_wifi_measures(self):
        session = self.db_master_session
        batch_size = 10
        measures = []
        for i in range(batch_size * 2):
            measures.append(WifiMeasure())
        session.add_all(measures)
        session.flush()
        start_id = measures[0].id

        blocks = schedule_wifimeasure_archival(batch=batch_size)
        self.assertEquals(len(blocks), 2)
        block = blocks[0]
        self.assertEquals(block,
                          (start_id, start_id + batch_size))

        block = blocks[1]
        self.assertEquals(block,
                          (start_id + batch_size, start_id + 2 * batch_size))

        blocks = schedule_wifimeasure_archival(batch=batch_size)
        self.assertEquals(len(blocks), 0)

    def test_backup_cell_to_s3(self):
        session = self.db_master_session
        batch_size = 10
        measures = []
        for i in range(batch_size):
            measures.append(CellMeasure())
        session.add_all(measures)
        session.flush()
        start_id = measures[0].id

        blocks = schedule_cellmeasure_archival(batch=batch_size)
        self.assertEquals(len(blocks), 1)
        block = blocks[0]
        self.assertEquals(block, (start_id, start_id + batch_size))

        with mock_s3():
            with patch.object(S3Backend,
                              'backup_archive', lambda x, y, z: True):
                zips = write_cellmeasure_s3_backups(cleanup_zip=False)
                self.assertTrue(len(zips), 1)
                fname = zips[0]
                myzip = ZipFile(fname)
                try:
                    contents = set(myzip.namelist())
                    expected_contents = set(['alembic_revision.txt',
                                             'cell_measure.csv'])
                    self.assertEquals(expected_contents, contents)
                finally:
                    myzip.close()

        blocks = session.query(MeasureBlock).all()

        self.assertEquals(len(blocks), 1)
        block = blocks[0]

        actual_sha = hashlib.sha1()
        actual_sha.update(open(fname, 'rb').read())
        self.assertEquals(block.archive_sha, actual_sha.digest())
        self.assertTrue(block.archive_date is not None)

    def test_backup_wifi_to_s3(self):
        session = self.db_master_session
        batch_size = 10
        measures = []
        for i in range(batch_size):
            measures.append(WifiMeasure())
        session.add_all(measures)
        session.flush()
        start_id = measures[0].id

        blocks = schedule_wifimeasure_archival(batch=batch_size)
        self.assertEquals(len(blocks), 1)
        block = blocks[0]
        self.assertEquals(block, (start_id, start_id + batch_size))

        with mock_s3():
            with patch.object(S3Backend,
                              'backup_archive', lambda x, y, z: True):
                zips = write_wifimeasure_s3_backups(cleanup_zip=False)
                self.assertTrue(len(zips), 1)
                fname = zips[0]
                myzip = ZipFile(fname)
                try:
                    contents = set(myzip.namelist())
                    expected_contents = set(['alembic_revision.txt',
                                             'wifi_measure.csv'])
                    self.assertEquals(expected_contents, contents)
                finally:
                    myzip.close()

        blocks = session.query(MeasureBlock).all()

        self.assertEquals(len(blocks), 1)
        block = blocks[0]

        actual_sha = hashlib.sha1()
        actual_sha.update(open(fname, 'rb').read())
        self.assertEquals(block.archive_sha, actual_sha.digest())
        self.assertTrue(block.archive_date is not None)

    def test_delete_cell_measures(self):
        session = self.db_master_session
        block = MeasureBlock()
        block.measure_type = MEASURE_TYPE['cell']
        block.start_id = 120
        block.end_id = 140
        block.s3_key = 'fake_key'
        block.archive_date = datetime.datetime.utcnow()
        session.add(block)

        for i in range(100, 150):
            session.add(CellMeasure(id=i))
        session.commit()

        with patch.object(S3Backend, 'check_archive', lambda x, y, z: True):
            delete_cellmeasure_records()
        self.assertEquals(session.query(CellMeasure).count(), 29)

    def test_delete_wifi_measures(self):
        session = self.db_master_session
        block = MeasureBlock()
        block.measure_type = MEASURE_TYPE['wifi']
        block.start_id = 120
        block.end_id = 140
        block.s3_key = 'fake_key'
        block.archive_date = datetime.datetime.utcnow()
        session.add(block)

        for i in range(100, 150):
            session.add(WifiMeasure(id=i))
        session.commit()

        with patch.object(S3Backend, 'check_archive', lambda x, y, z: True):
            delete_wifimeasure_records()
        self.assertEquals(session.query(WifiMeasure).count(), 29)
