from boto.s3.connection import S3Connection
import boto.s3.key
import hashlib
import os
import shutil
import tempfile


class S3Backend(object):
    def __init__(self, heka):
        from ichnaea import config
        conf = config()
        self.heka = heka
        self.access_key_id = conf.get('ichnaea', 'access_key_id')
        self.secret_access_key = conf.get('ichnaea', 'secret_access_key')
        self.bucket_name = conf.get('ichnaea', 's3_backup_bucket')

    def check_archive(self, expected_sha, s3_key):
        short_fname = os.path.split(s3_key)[-1]

        tmpdir = tempfile.mkdtemp()
        s3_copy = os.path.join(tmpdir, short_fname+".s3")

        try:
            conn = S3Connection(self.access_key_id, self.secret_access_key)
            bucket = conn.get_bucket(self.bucket_name)
            k = boto.s3.key.Key(bucket)
            k.key = s3_key
            k.get_contents_to_filename(s3_copy)

            # Compare
            s3 = hashlib.sha1()
            s3.update(open(s3_copy, 'rb').read())
            return s3.hexdigest() == expected_sha
        except Exception:
            self.heka.error('s3 verification error')
            return False
        finally:
            if os.path.exists(s3_copy):
                shutil.rmtree(s3_copy)

    def backup_archive(self, s3_key, fname, delete_on_write=False):
        try:
            conn = S3Connection(self.access_key_id, self.secret_access_key)
            bucket = conn.get_bucket(self.bucket_name)
            k = boto.s3.key.Key(bucket)
            k.key = s3_key
            k.set_contents_from_filename(fname)
            return True
        except Exception:
            self.heka.error('s3 write error')
            return False
