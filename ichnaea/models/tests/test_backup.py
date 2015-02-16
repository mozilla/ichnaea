from hashlib import sha1

from ichnaea.models.backup import (
    MeasureBlock,
    MeasureType,
)
from ichnaea.tests.base import DBTestCase
from ichnaea import util


class TestMeasureBlock(DBTestCase):

    def test_constructor(self):
        block = MeasureBlock()
        self.assertTrue(block.id is None)

    def test_fiels(self):
        archive_sha = sha1().digest()
        now = util.utcnow()
        s3_key = '201502/wifi_10_200.zip'

        block = MeasureBlock(
            measure_type=MeasureType.wifi, s3_key=s3_key,
            archive_date=now, archive_sha=archive_sha,
            start_id=10, end_id=200)

        session = self.db_master_session
        session.add(block)
        session.commit()

        result = session.query(MeasureBlock).first()
        self.assertTrue(result.id > 0)
        self.assertEqual(result.measure_type, MeasureType.wifi)
        self.assertEqual(result.s3_key, s3_key)
        self.assertEqual(result.archive_date, now)
        self.assertEqual(result.archive_sha, archive_sha)
        self.assertEqual(result.start_id, 10)
        self.assertEqual(result.end_id, 200)
