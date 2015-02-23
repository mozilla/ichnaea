from hashlib import sha1

from ichnaea.models.backup import (
    ObservationBlock,
    ObservationType,
)
from ichnaea.tests.base import DBTestCase
from ichnaea import util


class TestObservationBlock(DBTestCase):

    def test_fiels(self):
        archive_sha = sha1().digest()
        now = util.utcnow()
        s3_key = '201502/wifi_10_200.zip'

        session = self.db_master_session
        session.add(ObservationBlock(
            measure_type=ObservationType.wifi, s3_key=s3_key,
            archive_date=now, archive_sha=archive_sha,
            start_id=10, end_id=200))
        session.flush()

        result = session.query(ObservationBlock).first()
        self.assertTrue(result.id > 0)
        self.assertEqual(result.measure_type, ObservationType.wifi)
        self.assertEqual(result.s3_key, s3_key)
        self.assertEqual(result.archive_date, now)
        self.assertEqual(result.archive_sha, archive_sha)
        self.assertEqual(result.start_id, 10)
        self.assertEqual(result.end_id, 200)
