import boto
import hashlib
import os
import shutil
import tempfile


class S3Backend(object):
    def __init__(self, heka):
        from ichnaea import config
        conf = config()
        self.heka = heka
        self.bucket_name = conf.get('ichnaea', 's3_backup_bucket')
        self.s3_prefix = conf.get('ichnaea', 's3_key_prefix')

    def check_archive(self, expected_sha, s3_key):
        short_fname = os.path.split(s3_key)[-1]

        tmpdir = tempfile.mkdtemp()
        s3_copy = os.path.join(tmpdir, short_fname+".s3")

        try:
            conn = boto.connect_s3()
            bucket = conn.get_bucket(self.bucket_name, validate=False)
            k = boto.s3.key.Key(bucket)
            k.key = ''.join([self.s3_prefix, '/', s3_key])
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
            conn = boto.connect_s3()
            bucket = conn.get_bucket(self.bucket_name)
            k = boto.s3.key.Key(bucket)
            k.key = ''.join([self.s3_prefix, '/', s3_key])
            k.set_contents_from_filename(fname)
            return True
        except Exception:
            self.heka.error('s3 write error')
            return False
