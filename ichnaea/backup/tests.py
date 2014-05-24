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
    def setUp(self):
        super(TestMeasurementsDump, self).setUp()
        self.session = self.db_master_session
        self.START_ID = 49950
        self.batch_size = 100

    def test_journal_cell_measures(self):
        for i in range(self.batch_size * 2):
            cm = CellMeasure(id=i + self.START_ID)
            self.session.add(cm)
        self.session.commit()

        blocks = schedule_cellmeasure_archival()
        self.assertEquals(len(blocks), 2)
        block = blocks[0]
        self.assertEquals(block,
                          (self.START_ID,
                           self.START_ID + self.batch_size))

        block = blocks[1]
        self.assertEquals(block,
                          (self.START_ID + self.batch_size,
                           self.START_ID + 2 * self.batch_size))

        blocks = schedule_cellmeasure_archival()
        self.assertEquals(len(blocks), 0)

    def test_journal_wifi_measures(self):
        for i in range(self.batch_size * 2):
            cm = WifiMeasure(id=i + self.START_ID)
            self.session.add(cm)
        self.session.commit()

        blocks = schedule_wifimeasure_archival()
        self.assertEquals(len(blocks), 2)
        block = blocks[0]
        self.assertEquals(block,
                          (self.START_ID,
                           self.START_ID + self.batch_size))

        block = blocks[1]
        self.assertEquals(block,
                          (self.START_ID + self.batch_size,
                           self.START_ID + 2 * self.batch_size))

        blocks = schedule_wifimeasure_archival()
        self.assertEquals(len(blocks), 0)

    def test_backup_cell_to_s3(self):
        for i in range(self.batch_size):
            cm = CellMeasure(id=i + self.START_ID)
            self.session.add(cm)
        self.session.commit()

        blocks = schedule_cellmeasure_archival()
        self.assertEquals(len(blocks), 1)
        block = blocks[0]
        self.assertEquals(block,
                          (self.START_ID,
                           self.START_ID + self.batch_size))

        with mock_s3():
            with patch.object(S3Backend,
                              'backup_archive', lambda x, y, z: True):
                zips = write_cellmeasure_s3_backups(False)
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

        blocks = self.session.query(MeasureBlock).all()

        self.assertEquals(len(blocks), 1)
        block = blocks[0]

        actual_sha = hashlib.sha1()
        actual_sha.update(open(fname, 'rb').read())
        self.assertEquals(block.archive_sha, actual_sha.digest())

    def test_backup_wifi_to_s3(self):
        for i in range(self.batch_size):
            cm = WifiMeasure(id=i + self.START_ID)
            self.session.add(cm)
        self.session.commit()

        blocks = schedule_wifimeasure_archival()
        self.assertEquals(len(blocks), 1)
        block = blocks[0]
        self.assertEquals(block,
                          (self.START_ID,
                           self.START_ID + self.batch_size))

        with mock_s3():
            with patch.object(S3Backend,
                              'backup_archive', lambda x, y, z: True):
                zips = write_wifimeasure_s3_backups(False)
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

        blocks = self.session.query(MeasureBlock).all()

        self.assertEquals(len(blocks), 1)
        block = blocks[0]

        actual_sha = hashlib.sha1()
        actual_sha.update(open(fname, 'rb').read())
        self.assertEquals(block.archive_sha, actual_sha.digest())

    def test_delete_cell_measures(self):
        block = MeasureBlock()
        block.measure_type = MEASURE_TYPE['cell']
        block.start_id = 120
        block.end_id = 140
        block.s3_key = 'fake_key'
        block.archive_date = datetime.datetime.utcnow()
        self.session.add(block)

        for i in range(100, 150):
            self.session.add(CellMeasure(id=i))
        self.session.commit()

        with patch.object(S3Backend, 'check_archive', lambda x, y, z: True):
            delete_cellmeasure_records()
        self.assertEquals(self.session.query(CellMeasure).count(), 29)

    def test_delete_wifi_measures(self):
        block = MeasureBlock()
        block.measure_type = MEASURE_TYPE['wifi']
        block.start_id = 120
        block.end_id = 140
        block.s3_key = 'fake_key'
        block.archive_date = datetime.datetime.utcnow()
        self.session.add(block)

        for i in range(100, 150):
            self.session.add(WifiMeasure(id=i))
        self.session.commit()

        with patch.object(S3Backend, 'check_archive', lambda x, y, z: True):
            delete_wifimeasure_records()
        self.assertEquals(self.session.query(WifiMeasure).count(), 29)
