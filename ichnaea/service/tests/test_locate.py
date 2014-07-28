from ichnaea.geocalc import maximum_country_radius
from ichnaea.geoip import GeoIPMock
from ichnaea.models import (
    Cell,
    CELLID_LAC,
    GEOIP_CITY_ACCURACY,
    RADIO_TYPE,
    Wifi,
    WIFI_MIN_ACCURACY,
)
from ichnaea.tests.base import (
    DBTestCase,
    FREMONT_IP,
    FREMONT_LAT,
    FREMONT_LON,
    USA_MCC,
)
from ichnaea.service import locate


GB_IP = '192.168.0.1'
GB_LAT = 51.5
GB_LON = -0.1
GB_MCC = 234
GB_RADIUS = maximum_country_radius('GB')


class TestSearchAllSources(DBTestCase):

    @classmethod
    def setUpClass(cls):
        DBTestCase.setUpClass()
        cls.geoip_db = GeoIPMock({
            FREMONT_IP: {
                'latitude': FREMONT_LAT,
                'longitude': FREMONT_LON,
                'country_code': 'US',
                'city': True,
            },
            GB_IP: {
                'latitude': GB_LAT,
                'longitude': GB_LON,
                'country_code': 'GB',
                'city': False,
            },
        })

    @classmethod
    def tearDownClass(cls):
        del cls.geoip_db
        DBTestCase.tearDownClass()

    def test_no_data(self):
        result = locate.search_all_sources(
            self.db_slave_session, 'geolocate', {}, geoip_db=self.geoip_db)
        self.assertTrue(result is None)

        self.check_stats(
            counter=[
                'geolocate.no_country',
                'geolocate.no_geoip_found',
            ],
        )

    def test_geoip_unknown(self):
        result = locate.search_all_sources(
            self.db_slave_session, 'geolocate', {},
            client_addr='127.0.0.1', geoip_db=self.geoip_db)
        self.assertTrue(result is None)

        self.check_stats(
            counter=[
                'geolocate.no_country',
                'geolocate.no_geoip_found',
            ],
        )

    def test_geoip_city(self):
        result = locate.search_all_sources(
            self.db_slave_session, 'geolocate', {},
            client_addr=FREMONT_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': FREMONT_LAT,
                          'lon': FREMONT_LON,
                          'accuracy': GEOIP_CITY_ACCURACY})

        self.check_stats(
            counter=[
                'geolocate.country_from_geoip',
                'geolocate.geoip_city_found',
                'geolocate.geoip_hit',
            ],
        )

    def test_geoip_country(self):
        result = locate.search_all_sources(
            self.db_slave_session, 'geolocate', {},
            client_addr=GB_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': GB_RADIUS})

        self.check_stats(
            counter=[
                'geolocate.country_from_geoip',
                'geolocate.geoip_country_found',
                'geolocate.geoip_hit',
            ],
        )

    def test_geoip_mcc_match(self):
        session = self.db_slave_session
        gsm = RADIO_TYPE['gsm']
        cell = {'radio': gsm, 'mcc': GB_MCC, 'mnc': 1, 'lac': 1, 'cid': 1}
        session.add(Cell(**cell))
        session.flush()

        result = locate.search_all_sources(
            session, 'geolocate',
            {'cell': [cell]},
            client_addr=GB_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': GB_RADIUS})

        self.check_stats(
            counter=[
                'geolocate.country_from_geoip',
                'geolocate.geoip_country_found',
                'geolocate.geoip_hit',
            ],
        )

    def test_geoip_mcc_mismatch(self):
        session = self.db_slave_session
        gsm = RADIO_TYPE['gsm']
        cell = {'radio': gsm, 'mcc': USA_MCC, 'mnc': 1, 'lac': 1, 'cid': 1}
        session.add(Cell(**cell))
        session.flush()

        result = locate.search_all_sources(
            session, 'geolocate',
            {'cell': [cell]},
            client_addr=GB_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': GB_RADIUS})

        self.check_stats(
            counter=[
                'geolocate.anomaly.geoip_mcc_mismatch',
                'geolocate.country_from_geoip',
                'geolocate.geoip_country_found',
                'geolocate.geoip_hit',
            ],
        )

    def test_geoip_mcc_mismatch_unknown_cell(self):
        session = self.db_slave_session
        gsm = RADIO_TYPE['gsm']
        # We do not add the cell to the DB on purpose
        cell = {'radio': gsm, 'mcc': USA_MCC, 'mnc': 1, 'lac': 1, 'cid': 1}

        result = locate.search_all_sources(
            session, 'geolocate',
            {'cell': [cell]},
            client_addr=GB_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': GB_RADIUS})

        self.check_stats(
            counter=[
                'geolocate.anomaly.geoip_mcc_mismatch',
                'geolocate.country_from_geoip',
                'geolocate.geoip_country_found',
                'geolocate.geoip_hit',
            ],
        )

    def test_geoip_mcc_multiple(self):
        session = self.db_slave_session
        gsm = RADIO_TYPE['gsm']
        cell_key = {'radio': gsm, 'mnc': 1, 'lac': 1, 'cid': 1}
        cells = [
            dict(mcc=GB_MCC, **cell_key),
            dict(mcc=USA_MCC, **cell_key),
        ]
        for cell in cells:
            session.add(Cell(**cell))
        session.flush()

        result = locate.search_all_sources(
            session, 'geolocate',
            {'cell': cells},
            client_addr=GB_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': GB_RADIUS})

        self.check_stats(
            counter=[
                'geolocate.anomaly.multiple_mccs',
                'geolocate.country_from_geoip',
                'geolocate.geoip_country_found',
                'geolocate.geoip_hit',
            ],
        )

    def test_geoip_mcc_multiple_unknown_mismatching_cell(self):
        session = self.db_slave_session
        gsm = RADIO_TYPE['gsm']
        cell_key = {'radio': gsm, 'mnc': 1, 'lac': 1, 'cid': 1}
        cells = [
            dict(mcc=GB_MCC, **cell_key),
            dict(mcc=USA_MCC, **cell_key),
        ]
        # Only add the matching cell to the DB
        session.add(Cell(**cells[0]))
        session.flush()

        result = locate.search_all_sources(
            session, 'geolocate',
            {'cell': cells},
            client_addr=GB_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': GB_RADIUS})

        self.check_stats(
            counter=[
                'geolocate.anomaly.multiple_mccs',
                'geolocate.country_from_geoip',
                'geolocate.geoip_country_found',
                'geolocate.geoip_hit',
            ],
        )

    def test_cell(self):
        session = self.db_slave_session
        cell_key = {
            'radio': RADIO_TYPE['gsm'], 'mcc': GB_MCC, 'mnc': 1, 'lac': 1,
        }
        session.add(Cell(
            lat=GB_LAT, lon=GB_LON, range=6000, cid=1, **cell_key))
        session.add(Cell(
            lat=GB_LAT, lon=GB_LON, range=9000, cid=CELLID_LAC, **cell_key))
        session.flush()

        result = locate.search_all_sources(
            session, 'geolocate',
            {'cell': [dict(cid=1, **cell_key)]},
            client_addr=GB_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': 6000})

        self.check_stats(
            counter=[
                'geolocate.cell_found',
                'geolocate.cell_hit',
                'geolocate.cell_lac_found',
                'geolocate.country_from_geoip',
                'geolocate.geoip_country_found',
            ],
        )

    def test_wifi(self):
        session = self.db_slave_session
        wifis = [{'key': '001122334455'}, {'key': '112233445566'}]
        session.add(Wifi(
            key=wifis[0]['key'], lat=GB_LAT, lon=GB_LON, range=200))
        session.add(Wifi(
            key=wifis[1]['key'], lat=GB_LAT, lon=GB_LON + 0.00001, range=300))
        session.flush()

        result = locate.search_all_sources(
            session, 'geolocate',
            {'wifi': wifis},
            client_addr=GB_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON + 0.000005,
                          'accuracy': WIFI_MIN_ACCURACY})

        self.check_stats(
            counter=[
                'geolocate.wifi_found',
                'geolocate.wifi_hit',
                'geolocate.country_from_geoip',
                'geolocate.geoip_country_found',
            ],
        )
