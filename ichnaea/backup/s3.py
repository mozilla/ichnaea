import boto
import hashlib
import os
import shutil
import tempfile


def compute_hash(zip_path):
    sha = hashlib.sha1()
    with open(zip_path, 'rb') as file_in:
        while True:
            data = file_in.read(16384)
            if not data:
                break
            sha.update(data)
    return sha.digest()


class S3Backend(object):

    def __init__(self, backup_bucket, heka_client):
        self.heka_client = heka_client
        self.backup_bucket = backup_bucket

    def check_archive(self, expected_sha, s3_key):
        short_fname = os.path.split(s3_key)[-1]

        tmpdir = tempfile.mkdtemp()
        s3_copy = os.path.join(tmpdir, short_fname + ".s3")

        try:
            conn = boto.connect_s3()
            bucket = conn.get_bucket(self.backup_bucket, validate=False)
            k = boto.s3.key.Key(bucket)
            k.key = 'backups/' + s3_key
            k.get_contents_to_filename(s3_copy)

            # Compare
            s3_hash = compute_hash(s3_copy)
            return s3_hash == expected_sha
        except Exception:
            from binascii import hexlify
            msg = ('S3 verification error: SHA hash [%s]' %
                   hexlify(expected_sha))
            self.heka_client.error(msg)
            return False
        finally:
            if os.path.exists(tmpdir):
                shutil.rmtree(tmpdir)

    def backup_archive(self, s3_key, fname, delete_on_write=False):
        try:
            conn = boto.connect_s3()
            bucket = conn.get_bucket(self.backup_bucket)
            k = boto.s3.key.Key(bucket)
            k.key = 'backups/' + s3_key
            k.set_contents_from_filename(fname)
            return True
        except Exception:
            self.heka_client.error('s3 write error')
            return False
