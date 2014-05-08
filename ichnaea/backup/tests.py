from unittest2 import TestCase
from ichnaea.backup import S3Backend
from mock import patch, Mock
from boto.s3.connection import S3Connection
from boto.s3.key import Key
from contextlib import contextmanager


@contextmanager
def mock_s3():
    mock_conn = Mock()
    with patch.object(S3Connection, 'get_bucket', mock_conn):
        with patch.object(Key, 'set_contents_from_filename') as mock_key:
            yield mock_key


class TestBackup(TestCase):
    def test_backup(self):
        with mock_s3() as mock_key:
            s3 = S3Backend()
            s3.backup_archive('/tmp/not_a_real_file.zip')
            self.assertEquals(mock_key.call_args[0],
                              ('/tmp/not_a_real_file.zip',))
