from unittest2 import TestCase
from ichnaea.backup import S3Backend
from mock import patch, MagicMock, Mock
import boto
from contextlib import contextmanager


@contextmanager
def mock_s3():
    mock_conn = MagicMock()
    mock_key = MagicMock()
    with patch.object(boto, 'connect_s3', mock_conn):
        with patch('boto.s3.key.Key', lambda _: mock_key):
            yield mock_key


class TestBackup(TestCase):
    def test_backup(self):
        from ichnaea import config
        conf = config()
        prefix = conf.get('ichnaea', 's3_key_prefix')

        with mock_s3() as mock_key:
            s3 = S3Backend(Mock())

            s3.backup_archive('some_key', '/tmp/not_a_real_file.zip')
            self.assertEquals(mock_key.key, '/'.join([prefix, 'some_key']))
            method = mock_key.set_contents_from_filename
            self.assertEquals(method.call_args[0][0],
                              '/tmp/not_a_real_file.zip')
