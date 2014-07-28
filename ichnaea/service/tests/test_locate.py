import random

from ichnaea.geocalc import maximum_country_radius
from ichnaea.geoip import GeoIPMock
from ichnaea.models import (
    Cell,
    CELL_MIN_ACCURACY,
    CELLID_LAC,
    GEOIP_CITY_ACCURACY,
    LAC_MIN_ACCURACY,
    RADIO_TYPE,
    Wifi,
    WIFI_MIN_ACCURACY,
)
from ichnaea.tests.base import (
    BRAZIL_MCC,
    DBTestCase,
    FRANCE_MCC,
    FREMONT_IP,
    FREMONT_LAT,
    FREMONT_LON,
    PARIS_LAT,
    PARIS_LON,
    PORTO_ALEGRE_LAT,
    PORTO_ALEGRE_LON,
    SAO_PAULO_LAT,
    SAO_PAULO_LON,
    USA_MCC,
    VIVO_MNC,
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

    def test_cell_miss_lac_hit(self):
        session = self.db_slave_session
        lat = PARIS_LAT
        lon = PARIS_LON
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        umts = RADIO_TYPE['umts']
        data = [
            Cell(lat=lat, lon=lon, radio=umts, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=umts, cid=5, **key),
            Cell(lat=lat + 0.006, lon=lon + 0.006, radio=umts, cid=6, **key),
            Cell(lat=lat + 0.0026666, lon=lon + 0.0033333,
                 radio=umts, cid=CELLID_LAC,
                 range=500000, **key),
        ]
        session.add_all(data)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {"cell": [dict(radio="umts", cid=7, **key)]})

        self.assertEqual(result,
                         {'lat': PARIS_LAT + 0.0026666,
                          'lon': PARIS_LON + 0.0033333,
                          'accuracy': 500000})

    def test_cell_hit_ignores_lac(self):
        session = self.db_slave_session
        lat = PARIS_LAT
        lon = PARIS_LON
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        data = [
            Cell(lat=lat, lon=lon, radio=2, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=2, cid=5, **key),
            Cell(lat=lat + 0.006, lon=lon + 0.006, radio=2, cid=6, **key),
            Cell(lat=lat + 0.0026666,
                 lon=lon + 0.0033333, radio=2, cid=CELLID_LAC,
                 range=50000, **key),
        ]
        session.add_all(data)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {"cell": [dict(radio="umts", cid=5, **key)]})

        self.assertEqual(result,
                         {'lat': PARIS_LAT + 0.002,
                          'lon': PARIS_LON + 0.004,
                          'accuracy': CELL_MIN_ACCURACY})

    def test_lac_miss(self):
        session = self.db_slave_session
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        lat = PARIS_LAT
        lon = PARIS_LON
        gsm = RADIO_TYPE['gsm']
        data = [
            Cell(lat=lat, lon=lon, radio=gsm, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=gsm, cid=5, **key),
            Cell(lat=1.006, lon=1.006, radio=gsm, cid=6, **key),
            Cell(lat=1.0026666, lon=1.0033333, radio=gsm, cid=CELLID_LAC,
                 range=50000, **key),
        ]
        session.add_all(data)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {"cell": [dict(radio="gsm", mcc=FRANCE_MCC, mnc=2, lac=4, cid=5)]})

        self.assertTrue(result is None)

    def test_cell_ignore_invalid_lac_cid(self):
        session = self.db_slave_session
        lat = PARIS_LAT
        lon = PARIS_LON
        gsm = RADIO_TYPE['gsm']
        lte = RADIO_TYPE['lte']

        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        ignored_key = dict(mcc=FRANCE_MCC, mnc=2, lac=-1, cid=-1)

        data = [
            Cell(lat=lat, lon=lon, radio=gsm, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=gsm, cid=5, **key),
            Cell(lat=lat, lon=lon, radio=gsm, **ignored_key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=lte, **ignored_key),
        ]
        session.add_all(data)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {"cell": [
                dict(radio="gsm", cid=4, **key),
                dict(radio="gsm", cid=5, **key),

                dict(radio="gsm", cid=5, mcc=FRANCE_MCC, mnc=2, lac=-1),
                dict(radio="gsm", cid=-1, mcc=FRANCE_MCC, mnc=2, lac=3),
            ]})

        self.assertEqual(result,
                         {'lat': PARIS_LAT + 0.001,
                          'lon': PARIS_LON + 0.002,
                          'accuracy': CELL_MIN_ACCURACY})

    def test_cell_multiple_lac_hit(self):
        session = self.db_slave_session
        lat = PARIS_LAT
        lon = PARIS_LON
        gsm = RADIO_TYPE['gsm']

        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        key2 = dict(mcc=FRANCE_MCC, mnc=2, lac=4)

        data = [
            Cell(lat=lat + 0.2, lon=lon + 0.2, radio=gsm,
                 cid=CELLID_LAC, range=20000, **key),
            Cell(lat=lat + 0.2, lon=lon + 0.4, radio=gsm,
                 cid=5, range=1000, **key),
            Cell(lat=lat, lon=lon, radio=gsm,
                 cid=CELLID_LAC, range=30000, **key2),
            Cell(lat=lat + 0.02, lon=lon + 0.02, radio=gsm,
                 cid=4, range=2000, **key2),
            Cell(lat=lat + 0.04, lon=lon + 0.04, radio=gsm,
                 cid=5, range=3000, **key2),
        ]
        session.add_all(data)
        session.flush()

        # We have two lacs, both with two cells, but only know about
        # one cell in one of them and two in the other.
        # The lac with two known cells wins and we use both their
        # positions to calculate the final result.
        result = locate.search_all_sources(
            session, 'm',
            {"cell": [
                dict(radio="gsm", cid=4, **key),
                dict(radio="gsm", cid=9, **key),
                dict(radio="gsm", cid=4, **key2),
                dict(radio="gsm", cid=5, **key2),
            ]})

        self.assertEqual(result,
                         {'lat': PARIS_LAT + 0.03,
                          'lon': PARIS_LON + 0.03,
                          'accuracy': CELL_MIN_ACCURACY})

    def test_cell_multiple_lac_lower_range_wins(self):
        session = self.db_slave_session
        lat = PARIS_LAT
        lon = PARIS_LON
        gsm = RADIO_TYPE['gsm']

        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        key2 = dict(mcc=FRANCE_MCC, mnc=2, lac=4)

        data = [
            Cell(lat=lat + 0.2, lon=lon + 0.2, radio=gsm,
                 cid=CELLID_LAC, range=10000, **key),
            Cell(lat=lat + 0.2, lon=lon + 0.4, radio=gsm,
                 cid=4, range=4000, **key),
            Cell(lat=lat, lon=lon, radio=gsm,
                 cid=CELLID_LAC, range=20000, **key2),
            Cell(lat=lat + 0.02, lon=lon + 0.02, radio=gsm,
                 cid=4, range=2000, **key2),
        ]
        session.add_all(data)
        session.flush()

        # We have two lacs with each one known cell.
        # The lac with the smallest cell wins.
        result = locate.search_all_sources(
            session, 'm',
            {"cell": [
                dict(radio="gsm", cid=4, **key),
                dict(radio="gsm", cid=4, **key2),
            ]})

        self.assertEqual(result,
                         {'lat': PARIS_LAT + 0.02,
                          'lon': PARIS_LON + 0.02,
                          'accuracy': CELL_MIN_ACCURACY})

    def test_cell_multiple_radio_mixed_cell_lac_hit(self):
        session = self.db_slave_session
        lat = PARIS_LAT
        lon = PARIS_LON
        gsm = RADIO_TYPE['gsm']
        lte = RADIO_TYPE['lte']

        key = dict(mcc=FRANCE_MCC, mnc=3, lac=4)
        key2 = dict(mcc=FRANCE_MCC, mnc=2, lac=3)

        data = [
            Cell(lat=lat + 0.2, lon=lon + 0.2, radio=gsm,
                 cid=CELLID_LAC, range=3000, **key),
            Cell(lat=lat + 0.2, lon=lon + 0.4, radio=gsm,
                 cid=5, range=500, **key),
            Cell(lat=lat, lon=lon, radio=lte,
                 cid=CELLID_LAC, range=10000, **key2),
            Cell(lat=lat + 0.01, lon=lon + 0.02, radio=lte,
                 cid=4, range=2000, **key2),
        ]
        session.add_all(data)
        session.flush()

        # GSM lac-only hit (cid 9 instead of 5) and a LTE cell hit
        result = locate.search_all_sources(
            session, 'm',
            {"cell": [
                dict(radio="gsm", cid=9, **key),
                dict(radio="lte", cid=4, **key2),
            ]})

        self.assertEqual(result,
                         {'lat': PARIS_LAT + 0.01,
                          'lon': PARIS_LON + 0.02,
                          'accuracy': CELL_MIN_ACCURACY})

    def test_wifi_not_found_cell_fallback(self):
        session = self.db_slave_session
        lat = PARIS_LAT
        lon = PARIS_LON
        umts = RADIO_TYPE['umts']
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        data = [
            Wifi(key="abcd", lat=3, lon=3),
            Cell(lat=lat, lon=lon, radio=umts, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=umts, cid=5, **key),
        ]
        session.add_all(data)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {"cell": [
                dict(radio="umts", cid=4, **key),
                dict(radio="umts", cid=5, **key),
            ], "wifi": [{"key": "abcd"}, {"key": "cdef"}]})

        self.assertEqual(result,
                         {'lat': PARIS_LAT + 0.001,
                          'lon': PARIS_LON + 0.002,
                          'accuracy': CELL_MIN_ACCURACY})

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

    def test_cell_disagrees_with_country(self):
        # This test checks that when a cell is at a lat/lon that
        # is not in the country determined by mcc (say) we reject
        # the query. Really we should start filtering these out
        # on ingress as well, but this is a double-check.

        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        data = [
            Cell(lat=PARIS_LAT,
                 lon=PARIS_LON,
                 radio=RADIO_TYPE['gsm'], cid=6789, **key),
        ]
        session.add_all(data)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {"cell": [dict(radio="gsm", cid=6789, **key)]})

        self.assertTrue(result is None)

        self.check_stats(
            counter=[
                ('m.anomaly.cell_country_mismatch', 1),
                ('m.country_from_mcc', 1),
                ('m.cell_found', 1),
                ('m.no_cell_lac_found', 1),
            ]
        )

    def test_lac_disagrees_with_country(self):
        # This test checks that when a LAC is at a lat/lon that
        # is not in the country determined by mcc (say) we reject
        # the query. Really we should start filtering these out
        # on ingress as well, but this is a double-check.

        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        data = [
            Cell(lat=PARIS_LAT,
                 lon=PARIS_LON,
                 radio=RADIO_TYPE['gsm'], cid=CELLID_LAC, **key),
        ]
        session.add_all(data)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {"cell": [dict(radio="gsm", cid=6789, **key)]})

        self.assertTrue(result is None)

        self.check_stats(
            counter=[
                ('m.anomaly.cell_lac_country_mismatch', 1),
                ('m.country_from_mcc', 1),
                ('m.no_cell_found', 1),
                ('m.cell_lac_found', 1),
            ]
        )

    def test_wifi_disagrees_with_country(self):
        # This test checks that when a wifi is at a lat/lon that
        # is not in the country determined by geoip, we drop back
        # to the geoip, rejecting the wifi.

        session = self.db_slave_session

        # This lat/lon is Paris, France
        (lat, lon) = (PARIS_LAT, PARIS_LON)

        wifi1 = dict(key="1234567890ab")
        wifi2 = dict(key="1234890ab567")
        wifi3 = dict(key="4321890ab567")
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
        ]
        session.add_all(data)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {"wifi": [wifi1, wifi2, wifi3]},
            client_addr=FREMONT_IP, geoip_db=self.geoip_db
        )

        self.assertEqual(result,
                         {'lat': FREMONT_LAT,
                          'lon': FREMONT_LON,
                          'accuracy': GEOIP_CITY_ACCURACY})

        self.check_stats(
            counter=[
                ('m.anomaly.wifi_country_mismatch', 1),
                ('m.country_from_geoip', 1),
                ('m.geoip_city_found', 1),
                ('m.wifi_found', 1),
                ('m.geoip_hit', 1),
            ]
        )

    def test_cell_disagrees_with_lac(self):
        # This test checks that when a cell is at a lat/lon that
        # is not in the LAC associated with it, we drop back
        # to the LAC. This likely represents some kind of internal
        # database consistency error, but it might also just be a
        # new cell that hasn't been integrated yet or something.

        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        data = [
            Cell(lat=PORTO_ALEGRE_LAT,
                 lon=PORTO_ALEGRE_LON,
                 radio=RADIO_TYPE['gsm'], cid=6789, **key),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 radio=RADIO_TYPE['gsm'], cid=CELLID_LAC, **key),
        ]
        session.add_all(data)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {"cell": [dict(radio="gsm", cid=6789, **key)]},
        )

        self.assertEqual(result,
                         {'lat': SAO_PAULO_LAT,
                          'lon': SAO_PAULO_LON,
                          'accuracy': LAC_MIN_ACCURACY})

        self.check_stats(
            counter=[
                ('m.anomaly.cell_cell_lac_mismatch', 1),
                ('m.country_from_mcc', 1),
                ('m.cell_lac_found', 1),
                ('m.cell_found', 1),
                ('m.cell_lac_hit', 1),
            ]
        )

    def test_wifi_disagrees_with_lac(self):
        # This test checks that when a wifi is at a lat/lon that
        # is not in the LAC associated with our query, we drop back
        # to the LAC.

        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        wifi1 = dict(key="1234567890ab")
        wifi2 = dict(key="1234890ab567")
        wifi3 = dict(key="4321890ab567")
        lat = PORTO_ALEGRE_LAT
        lon = PORTO_ALEGRE_LON
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 radio=RADIO_TYPE['gsm'], cid=CELLID_LAC, **key),
        ]
        session.add_all(data)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {"cell": [dict(radio="gsm", cid=6789, **key)],
             "wifi": [wifi1, wifi2, wifi3]},
        )

        self.assertEqual(result,
                         {'lat': SAO_PAULO_LAT,
                          'lon': SAO_PAULO_LON,
                          'accuracy': LAC_MIN_ACCURACY})

        self.check_stats(
            counter=[
                ('m.anomaly.wifi_cell_lac_mismatch', 1),
                ('m.country_from_mcc', 1),
                ('m.cell_lac_found', 1),
                ('m.wifi_found', 1),
                ('m.cell_lac_hit', 1),
            ]
        )

    def test_wifi_disagrees_with_cell(self):
        # This test checks that when a wifi is at a lat/lon that
        # is not in the cell associated with our query, we drop back
        # to the cell.

        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        wifi1 = dict(key="1234567890ab")
        wifi2 = dict(key="1234890ab567")
        wifi3 = dict(key="4321890ab567")
        lat = PORTO_ALEGRE_LAT
        lon = PORTO_ALEGRE_LON
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 radio=RADIO_TYPE['gsm'], cid=6789, **key),
        ]
        session.add_all(data)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {"cell": [dict(radio="gsm", cid=6789, **key)],
             "wifi": [wifi1, wifi2, wifi3]},
        )

        self.assertEqual(result,
                         {'lat': SAO_PAULO_LAT,
                          'lon': SAO_PAULO_LON,
                          'accuracy': CELL_MIN_ACCURACY})

        self.check_stats(
            counter=[
                ('m.anomaly.wifi_cell_mismatch', 1),
                ('m.country_from_mcc', 1),
                ('m.no_cell_lac_found', 1),
                ('m.cell_found', 1),
                ('m.wifi_found', 1),
                ('m.cell_hit', 1),
            ]
        )

    def test_cell_agrees_with_lac(self):
        # This test checks that when a cell is at a lat/lon that
        # is inside its enclosing LAC, we accept it and tighten
        # our accuracy accordingly.

        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        data = [
            Cell(lat=SAO_PAULO_LAT + 0.002,
                 lon=SAO_PAULO_LON + 0.002,
                 radio=RADIO_TYPE['gsm'], cid=6789, **key),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 radio=RADIO_TYPE['gsm'], cid=CELLID_LAC, **key),
        ]
        session.add_all(data)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {"cell": [dict(radio="gsm", cid=6789, **key)]},
        )

        self.assertEqual(result,
                         {'lat': SAO_PAULO_LAT + 0.002,
                          'lon': SAO_PAULO_LON + 0.002,
                          'accuracy': CELL_MIN_ACCURACY})

        self.check_stats(
            counter=[
                ('m.country_from_mcc', 1),
                ('m.cell_lac_found', 1),
                ('m.cell_found', 1),
                ('m.cell_hit', 1),
            ]
        )

    def test_wifi_agrees_with_cell(self):
        # This test checks that when a wifi is at a lat/lon that
        # is inside its enclosing cell, we accept it and tighten
        # our accuracy accordingly.

        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        wifi1 = dict(key="1234567890ab")
        wifi2 = dict(key="1234890ab567")
        wifi3 = dict(key="4321890ab567")
        lat = SAO_PAULO_LAT + 0.002
        lon = SAO_PAULO_LON + 0.002
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 radio=RADIO_TYPE['gsm'], cid=6789, **key),
        ]
        session.add_all(data)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {"cell": [dict(radio="gsm", cid=6789, **key)],
             "wifi": [wifi1, wifi2, wifi3]},
        )

        self.assertEqual(result,
                         {'lat': SAO_PAULO_LAT + 0.002,
                          'lon': SAO_PAULO_LON + 0.002,
                          'accuracy': WIFI_MIN_ACCURACY})

        self.check_stats(
            counter=[
                ('m.country_from_mcc', 1),
                ('m.no_cell_lac_found', 1),
                ('m.wifi_found', 1),
                ('m.cell_found', 1),
                ('m.wifi_hit', 1),
            ]
        )

    def test_wifi_agrees_with_lac(self):
        # This test checks that when a wifi is at a lat/lon that
        # is inside its enclosing LAC, we accept it and tighten
        # our accuracy accordingly.

        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        wifi1 = dict(key="1234567890ab")
        wifi2 = dict(key="1234890ab567")
        wifi3 = dict(key="4321890ab567")
        lat = SAO_PAULO_LAT + 0.002
        lon = SAO_PAULO_LON + 0.002
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 radio=RADIO_TYPE['gsm'], cid=CELLID_LAC, **key),
        ]
        session.add_all(data)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {"cell": [dict(radio="gsm", cid=6789, **key)],
             "wifi": [wifi1, wifi2, wifi3]},
        )

        self.assertEqual(result,
                         {'lat': SAO_PAULO_LAT + 0.002,
                          'lon': SAO_PAULO_LON + 0.002,
                          'accuracy': WIFI_MIN_ACCURACY})

        self.check_stats(
            counter=[
                ('m.country_from_mcc', 1),
                ('m.no_cell_found', 1),
                ('m.wifi_found', 1),
                ('m.cell_lac_found', 1),
                ('m.wifi_hit', 1),
            ]
        )

    def test_wifi_agrees_with_cell_and_lac(self):
        # This test checks that when a wifi is at a lat/lon that
        # is inside its enclosing LAC and cell, we accept it and
        # tighten our accuracy accordingly.

        session = self.db_slave_session
        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        wifi1 = dict(key="1234567890ab")
        wifi2 = dict(key="1234890ab567")
        wifi3 = dict(key="4321890ab567")
        lat = SAO_PAULO_LAT + 0.002
        lon = SAO_PAULO_LON + 0.002
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 radio=RADIO_TYPE['gsm'], cid=6789, **key),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 radio=RADIO_TYPE['gsm'], cid=CELLID_LAC, **key),
        ]
        session.add_all(data)
        session.flush()

        result = locate.search_all_sources(
            session, 'm',
            {"cell": [dict(radio="gsm", cid=6789, **key)],
             "wifi": [wifi1, wifi2, wifi3]},
        )

        self.assertEqual(result,
                         {'lat': SAO_PAULO_LAT + 0.002,
                          'lon': SAO_PAULO_LON + 0.002,
                          'accuracy': WIFI_MIN_ACCURACY})

        self.check_stats(
            counter=[
                ('m.country_from_mcc', 1),
                ('m.wifi_found', 1),
                ('m.cell_found', 1),
                ('m.cell_lac_found', 1),
                ('m.wifi_hit', 1),
            ]
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
