from sqlalchemy.exc import IntegrityError

from ichnaea.models.wifi import (
    Wifi,
    WifiBlacklist,
)
from ichnaea.tests.base import (
    DBTestCase,
    GB_LAT,
    GB_LON,
)


class TestWifi(DBTestCase):

    def test_fields(self):
        session = self.db_master_session
        session.add(Wifi(
            key='3680873e9b83', lat=GB_LAT, lon=GB_LON, range=200))
        session.flush()

        result = session.query(Wifi).first()
        self.assertEqual(result.key, '3680873e9b83')
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.range, 200)


class TestWifiBlacklist(DBTestCase):

    def test_fields(self):
        session = self.db_master_session
        session.add(WifiBlacklist(key='3680873e9b83', count=2))
        session.flush()

        result = session.query(WifiBlacklist).first()
        self.assertEqual(result.key, '3680873e9b83')
        self.assertEqual(result.count, 2)

    def test_unique_key(self):
        session = self.db_master_session
        session.add(WifiBlacklist(key='3680873e9b83'))
        session.flush()

        session.add(WifiBlacklist(key='3680873e9b83'))
        self.assertRaises(IntegrityError, session.flush)
