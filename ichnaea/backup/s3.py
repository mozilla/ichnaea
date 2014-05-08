from boto.s3.connection import S3Connection
from boto.s3.key import Key
import os
import datetime


class S3Backend(object):
    def __init__(self):
        from ichnaea import config
        conf = config()

        self.access_key_id = conf.get('ichnaea', 'access_key_id')
        self.secret_access_key = conf.get('ichnaea', 'secret_access_key')
        self.bucket_name = conf.get('ichnaea', 's3_backup_bucket')
        self.year_month = datetime.date.today().strftime("%Y%m")

    def backup_archive(self, fname):
        short_fname = os.path.split(fname)[-1]

        conn = S3Connection(self.access_key_id, self.secret_access_key)
        bucket = conn.get_bucket(self.bucket_name)
        k = Key(bucket)
        k.key = self.year_month + "/" + short_fname
        k.set_contents_from_filename(fname)

