from unittest2 import TestCase
from ichnaea.backup import S3Backend
from mock import patch, MagicMock, Mock
from boto.s3.connection import S3Connection
from contextlib import contextmanager


@contextmanager
def mock_s3():
    mock_conn = MagicMock()
    mock_key = MagicMock()
    with patch.object(S3Connection, 'get_bucket', mock_conn):
        with patch('boto.s3.key.Key', lambda _: mock_key):
            yield mock_key


class TestBackup(TestCase):
    def test_backup(self):
        with mock_s3() as mock_key:
            s3 = S3Backend(Mock())
            s3.backup_archive('some_key', '/tmp/not_a_real_file.zip')
            self.assertEquals(mock_key.key, 'some_key')
            method = mock_key.set_contents_from_filename
            self.assertEquals(method.call_args[0][0], '/tmp/not_a_real_file.zip')
