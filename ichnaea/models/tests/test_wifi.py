from sqlalchemy.exc import IntegrityError

from ichnaea.models.wifi import (
    Wifi,
    WifiBlocklist,
)
from ichnaea.tests.base import (
    DBTestCase,
    GB_LAT,
    GB_LON,
)


class TestWifi(DBTestCase):

    def test_fields(self):
        self.session.add(Wifi.create(
            key='3680873e9b83', lat=GB_LAT, lon=GB_LON, range=200))
        self.session.flush()

        result = self.session.query(Wifi).first()
        self.assertEqual(result.key, '3680873e9b83')
        self.assertEqual(result.lat, GB_LAT)
        self.assertEqual(result.lon, GB_LON)
        self.assertEqual(result.range, 200)


class TestWifiBlocklist(DBTestCase):

    def test_fields(self):
        self.session.add(WifiBlocklist(key='3680873e9b83', count=2))
        self.session.flush()

        result = self.session.query(WifiBlocklist).first()
        self.assertEqual(result.key, '3680873e9b83')
        self.assertEqual(result.count, 2)

    def test_unique_key(self):
        self.session.add(WifiBlocklist(key='3680873e9b83'))
        self.session.flush()

        self.session.add(WifiBlocklist(key='3680873e9b83'))
        self.assertRaises(IntegrityError, self.session.flush)
