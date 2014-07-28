import random

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
            self.db_slave_session, 'm', {},
            client_addr=None, geoip_db=self.geoip_db)
        self.assertTrue(result is None)

        self.check_stats(
            counter=[
                'm.no_country',
                'm.no_geoip_found',
            ],
        )

    def test_geoip_unknown(self):
        result = locate.search_all_sources(
            self.db_slave_session, 'm', {},
            client_addr='127.0.0.1', geoip_db=self.geoip_db)
        self.assertTrue(result is None)

        self.check_stats(
            counter=[
                'm.no_country',
                'm.no_geoip_found',
            ],
        )

    def test_geoip_city(self):
        result = locate.search_all_sources(
            self.db_slave_session, 'm', {},
            client_addr=FREMONT_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': FREMONT_LAT,
                          'lon': FREMONT_LON,
                          'accuracy': GEOIP_CITY_ACCURACY})

        self.check_stats(
            counter=[
                'm.country_from_geoip',
                'm.geoip_city_found',
                'm.geoip_hit',
            ],
        )

    def test_geoip_country(self):
        result = locate.search_all_sources(
            self.db_slave_session, 'm', {},
            client_addr=GB_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': GB_RADIUS})

        self.check_stats(
            counter=[
                'm.country_from_geoip',
                'm.geoip_country_found',
                'm.geoip_hit',
            ],
        )

    def test_geoip_mcc_match(self):
        session = self.db_slave_session
        gsm = RADIO_TYPE['gsm']
        cell = {'radio': gsm, 'mcc': GB_MCC, 'mnc': 1, 'lac': 1, 'cid': 1}
        session.add(Cell(**cell))
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {'cell': [cell]},
            client_addr=GB_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': GB_RADIUS})

        self.check_stats(
            counter=[
                'm.country_from_geoip',
                'm.geoip_country_found',
            ],
        )

    def test_geoip_mcc_mismatch(self):
        session = self.db_slave_session
        gsm = RADIO_TYPE['gsm']
        cell = {'radio': gsm, 'mcc': USA_MCC, 'mnc': 1, 'lac': 1, 'cid': 1}
        session.add(Cell(**cell))
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {'cell': [cell]},
            client_addr=GB_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': GB_RADIUS})

        self.check_stats(
            counter=[
                'm.anomaly.geoip_mcc_mismatch',
            ],
        )

    def test_geoip_mcc_mismatch_unknown_cell(self):
        session = self.db_slave_session
        gsm = RADIO_TYPE['gsm']
        # We do not add the cell to the DB on purpose
        cell = {'radio': gsm, 'mcc': USA_MCC, 'mnc': 1, 'lac': 1, 'cid': 1}

        result = locate.search_all_sources(
            session, 'm',
            {'cell': [cell]},
            client_addr=GB_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': GB_RADIUS})

        self.check_stats(
            counter=[
                'm.anomaly.geoip_mcc_mismatch',
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
            session, 'm',
            {'cell': cells},
            client_addr=GB_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': GB_RADIUS})

        self.check_stats(
            counter=[
                'm.anomaly.multiple_mccs',
                'm.country_from_geoip',
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
            session, 'm',
            {'cell': cells},
            client_addr=GB_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': GB_RADIUS})

        self.check_stats(
            counter=[
                'm.anomaly.multiple_mccs',
                'm.country_from_geoip',
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
            session, 'm',
            {'cell': [dict(cid=1, **cell_key)]},
            client_addr=GB_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': 6000})

        self.check_stats(
            counter=[
                'm.cell_found',
                'm.cell_hit',
                'm.cell_lac_found',
            ],
        )

    def test_cell_multiple_country_codes_from_mcc(self):
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
            session, 'm',
            {'cell': [dict(cid=1, **cell_key)]},
            client_addr=None, geoip_db=self.geoip_db)

        # Without a GeoIP, the mcc results in 4 different equally common
        # mcc values, GB not being the first one. We need to make sure
        # that we accept any of the country codes as a possible match
        # and don't discard otherwise good cell data based on this.
        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': 6000})

        self.check_stats(
            counter=[
                'm.cell_found',
                'm.cell_hit',
                'm.cell_lac_found',
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
            session, 'm',
            {'wifi': wifis},
            client_addr=GB_IP, geoip_db=self.geoip_db)

        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON + 0.000005,
                          'accuracy': WIFI_MIN_ACCURACY})

        self.check_stats(
            counter=[
                'm.wifi_found',
                'm.wifi_hit',
            ],
        )

    def test_wifi_too_few_candidates(self):
        session = self.db_slave_session
        wifis = [
            Wifi(key="001122334455", lat=1.0, lon=1.0),
            Wifi(key="112233445566", lat=1.001, lon=1.002),
        ]
        session.add_all(wifis)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {'wifi': [{"key": "001122334455"}]})

        self.assertTrue(result is None)
        self.check_stats(
            counter=[
                'm.miss',
                'm.no_wifi_found',
            ],
        )

    def test_wifi_too_few_matches(self):
        session = self.db_slave_session
        wifis = [
            Wifi(key="001122334455", lat=1.0, lon=1.0),
            Wifi(key="112233445566", lat=1.001, lon=1.002),
            Wifi(key="223344556677", lat=None, lon=None),
        ]
        session.add_all(wifis)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {'wifi': [{"key": "001122334455"}, {"key": "223344556677"}]})

        self.assertTrue(result is None)
        self.check_stats(
            counter=[
                'm.miss',
                'm.no_wifi_found',
            ],
        )

    def test_wifi_ignore_outlier(self):
        session = self.db_slave_session
        wifis = [
            Wifi(key="001122334455", lat=1.0, lon=1.0),
            Wifi(key="112233445566", lat=1.001, lon=1.002),
            Wifi(key="223344556677", lat=1.002, lon=1.004),
            Wifi(key="334455667788", lat=2.0, lon=2.0),
        ]
        session.add_all(wifis)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {'wifi': [
                {"key": "001122334455"}, {"key": "112233445566"},
                {"key": "223344556677"}, {"key": "334455667788"},
            ]})

        self.assertEqual(result,
                         {'lat': 1.001,
                          'lon': 1.002,
                          'accuracy': 248.6090897})

    def test_wifi_prefer_cluster_with_better_signals(self):
        session = self.db_slave_session
        wifis = [
            Wifi(key="A1", lat=1.0, lon=1.0),
            Wifi(key="B2", lat=1.001, lon=1.002),
            Wifi(key="C3", lat=1.002, lon=1.004),
            Wifi(key="D4", lat=2.0, lon=2.0),
            Wifi(key="E5", lat=2.001, lon=2.002),
            Wifi(key="F6", lat=2.002, lon=2.004),
        ]
        session.add_all(wifis)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {'wifi': [
                {"key": "A1", "signal": -100},
                {"key": "D4", "signal": -80},
                {"key": "B2", "signal": -100},
                {"key": "E5", "signal": -90},
                {"key": "C3", "signal": -100},
                {"key": "F6", "signal": -54},
            ]})

        self.assertEqual(result,
                         {'lat': 2.001,
                          'lon': 2.002,
                          'accuracy': 248.51819})

    def test_wifi_prefer_larger_cluster_over_high_signal(self):
        session = self.db_slave_session
        wifis = [Wifi(key="A%d" % i,
                      lat=1 + i * 0.000010,
                      lon=1 + i * 0.000012)
                 for i in range(5)]
        wifis += [
            Wifi(key="D4", lat=2.0, lon=2.0),
            Wifi(key="E5", lat=2.001, lon=2.002),
            Wifi(key="F6", lat=2.002, lon=2.004),
        ]
        session.add_all(wifis)
        session.flush()

        measures = [dict(key="A%d" % i,
                         signal=-80)
                    for i in range(5)]
        measures += [
            dict(key="D4", signal=-75),
            dict(key="E5", signal=-74),
            dict(key="F6", signal=-73)
        ]
        random.shuffle(measures)

        result = locate.search_all_sources(
            session, 'm',
            {'wifi': measures})

        self.assertEqual(result,
                         {'lat': 1.00002,
                          'lon': 1.000024,
                          'accuracy': WIFI_MIN_ACCURACY})

    def test_wifi_only_use_top_five_signals_in_noisy_cluster(self):
        session = self.db_slave_session
        # all these should wind up in the same cluster since
        # clustering threshold is 500m and the 10 wifis are
        # spaced in increments of (+1m, +1.2m)
        wifis = [Wifi(key="A%d" % i,
                      lat=1 + i * 0.000010,
                      lon=1 + i * 0.000012)
                 for i in range(10)]
        session.add_all(wifis)
        session.commit()
        measures = [dict(key="A%d" % i,
                         signal=-80)
                    for i in range(5, 10)]
        measures += [
            dict(key="A0", signal=-75),
            dict(key="A1", signal=-74),
            dict(key="A2", signal=-73),
            dict(key="A3", signal=-72),
            dict(key="A4", signal=-71),
        ]
        random.shuffle(measures)

        result = locate.search_all_sources(
            session, 'm',
            {'wifi': measures})

        self.assertEqual(result,
                         {'lat': 1.00002,
                          'lon': 1.000024,
                          'accuracy': WIFI_MIN_ACCURACY})

    def test_wifi_not_closeby(self):
        session = self.db_slave_session
        wifis = [
            Wifi(key="A1", lat=1.0, lon=1.0),
            Wifi(key="B2", lat=1.001, lon=1.002),
            Wifi(key="C3", lat=2.002, lon=2.004),
            Wifi(key="D4", lat=2.0, lon=2.0),
        ]
        session.add_all(wifis)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {'wifi': [{"key": "A1"}, {"key": "C3"}]})

        self.assertTrue(result is None)
