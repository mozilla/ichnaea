from boto.s3.connection import S3Connection
import boto.s3.key
import hashlib
import os
import shutil


class S3Backend(object):
    def __init__(self, heka):
        from ichnaea import config
        conf = config()
        self.heka = heka
        self.access_key_id = conf.get('ichnaea', 'access_key_id')
        self.secret_access_key = conf.get('ichnaea', 'secret_access_key')
        self.bucket_name = conf.get('ichnaea', 's3_backup_bucket')

    def backup_and_check(self, s3_key, fname):
        if self.backup_archive(s3_key, fname):
            if self.check_archive(fname):
                return True
        return False

    def check_archive(self, fname):
        short_fname = os.path.split(fname)[-1]
        s3_filename = fname+".s3"

        try:
            conn = S3Connection(self.access_key_id, self.secret_access_key)
            bucket = conn.get_bucket(self.bucket_name)
            k = boto.s3.key.Key(bucket)
            k.key = short_fname
            k.get_contents_to_filename(s3_filename)

            # Compare
            orig = hashlib.sha1()
            orig.update(open(fname, 'rb').read())

            s3 = hashlib.sha1()
            s3.update(open(fname, 'rb').read())
            return s3.digest() == orig.digest()
        except Exception:
            self.heka.error('s3 verification error')
            return False
        finally:
            if os.path.exists(s3_filename):
                shutil.rmtree(s3_filename)

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
