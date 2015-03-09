import random

from ichnaea.constants import (
    CELL_MIN_ACCURACY,
    LAC_MIN_ACCURACY,
    WIFI_MIN_ACCURACY,
)
from ichnaea.models import (
    Cell,
    CellArea,
    OCIDCell,
    OCIDCellArea,
    Radio,
    ValidCellKeySchema,
    Wifi,
)
from ichnaea.tests.base import (
    BRAZIL_MCC,
    BHUTAN_MCC,
    DBTestCase,
    FRANCE_MCC,
    FREMONT_LAT,
    FREMONT_LON,
    GB_LAT,
    GB_LON,
    GB_MCC,
    GeoIPIsolation,
    PARIS_LAT,
    PARIS_LON,
    PORTO_ALEGRE_LAT,
    PORTO_ALEGRE_LON,
    SAO_PAULO_LAT,
    SAO_PAULO_LON,
    USA_MCC,
    VIVO_MNC,
)
from ichnaea.locate import locate


class BaseLocateTest(DBTestCase, GeoIPIsolation):

    default_session = 'db_ro_session'
    searcher = None

    @classmethod
    def setUpClass(cls):
        DBTestCase.setUpClass()
        GeoIPIsolation.setup_geoip(raven_client=cls.raven_client)

    @classmethod
    def tearDownClass(cls):
        GeoIPIsolation.teardown_geoip()
        DBTestCase.tearDownClass()

    def _make_query(self, data=None, client_addr=None,
                    api_key_log=False, api_key_name='test'):
        if data is None:
            data = {'geoip': None, 'cell': [], 'wifi': []}
        if client_addr:
            data['geoip'] = client_addr
        return self.searcher(
            {'geoip': self.geoip_db, 'session': self.session},
            api_key_log=api_key_log,
            api_key_name=api_key_name,
            api_name='m',
        ).search(data)


class TestPositionSearcher(BaseLocateTest):

    searcher = locate.PositionSearcher

    def test_no_data(self):
        with self.db_call_checker() as check_db_calls:
            result = self._make_query()
            check_db_calls(rw=0, ro=0)

        self.assertTrue(result is None)
        self.check_stats(
            counter=[
                'm.miss',
            ],
        )

    def test_geoip_unknown(self):
        result = self._make_query(client_addr='127.0.0.1', api_key_log=True)
        self.assertTrue(result is None)

        self.check_stats(
            counter=[
                'm.api_log.test.geoip_miss',
            ],
        )

    def test_geoip_city(self):
        london = self.geoip_data['London']
        result = self._make_query(client_addr=london['ip'], api_key_log=True)
        self.assertEqual(result,
                         {'lat': london['latitude'],
                          'lon': london['longitude'],
                          'accuracy': london['accuracy']})

        self.check_stats(
            counter=[
                'm.geoip_city_found',
                'm.geoip_hit',
                'm.api_log.test.geoip_hit',
            ],
        )

    def test_geoip_country(self):
        bhutan = self.geoip_data['Bhutan']
        result = self._make_query(client_addr=bhutan['ip'], api_key_log=True)
        self.assertEqual(result,
                         {'lat': bhutan['latitude'],
                          'lon': bhutan['longitude'],
                          'accuracy': bhutan['accuracy']})

        self.check_stats(
            counter=[
                'm.geoip_country_found',
                'm.geoip_hit',
                'm.api_log.test.geoip_hit',
            ],
        )

    def test_geoip_mcc_match(self):
        london = self.geoip_data['London']
        cell = {'mcc': GB_MCC, 'mnc': 1, 'lac': 1, 'cid': 1}
        self.session.add(Cell(range=1000, radio=Radio.gsm, **cell))
        self.session.flush()

        result = self._make_query(
            data={'cell': [dict(radio=Radio.gsm.name, **cell)]},
            client_addr=london['ip'])
        self.assertEqual(result,
                         {'lat': london['latitude'],
                          'lon': london['longitude'],
                          'accuracy': london['accuracy']})

        self.check_stats(
            counter=[
                'm.geoip_city_found',
            ],
        )

    def test_geoip_mcc_mismatch(self):
        bhutan = self.geoip_data['Bhutan']
        key = {'mcc': USA_MCC, 'mnc': 1, 'lac': 1, 'cid': 1}
        key2 = {'mcc': USA_MCC, 'mnc': 1, 'lac': 1, }
        self.session.add(Cell(radio=Radio.gsm, lat=FREMONT_LAT,
                              lon=FREMONT_LON, range=1000, **key))
        self.session.add(CellArea(radio=Radio.gsm, lat=FREMONT_LAT,
                                  lon=FREMONT_LON, range=10000, **key2))
        self.session.flush()

        result = self._make_query(
            data={'cell': [dict(radio='Radio.gsm', **key)]},
            client_addr=bhutan['ip'])
        self.assertEqual(result,
                         {'lat': FREMONT_LAT,
                          'lon': FREMONT_LON,
                          'accuracy': CELL_MIN_ACCURACY})

    def test_geoip_mcc_mismatch_unknown_cell(self):
        london = self.geoip_data['London']
        # We do not add the cell to the DB on purpose
        cell = {'radio': Radio.gsm.name, 'mcc': USA_MCC, 'mnc': 1,
                'lac': 1, 'cid': 1}

        result = self._make_query(data={'cell': [cell]},
                                  client_addr=london['ip'])
        self.assertEqual(result,
                         {'lat': london['latitude'],
                          'lon': london['longitude'],
                          'accuracy': london['accuracy']})

    def test_geoip_mcc_multiple(self):
        london = self.geoip_data['London']
        cell_key = {'mnc': 1, 'lac': 1, 'cid': 1}
        cells = [
            dict(mcc=GB_MCC, **cell_key),
            dict(mcc=USA_MCC, **cell_key),
        ]
        for cell in cells:
            self.session.add(Cell(range=1000, radio=Radio.gsm, **cell))
        self.session.flush()

        result = self._make_query(
            data={'cell': [dict(radio=Radio.gsm.name, **cell)
                           for cell in cells]},
            client_addr=london['ip'])
        self.assertEqual(result,
                         {'lat': london['latitude'],
                          'lon': london['longitude'],
                          'accuracy': london['accuracy']})

    def test_geoip_mcc_multiple_unknown_mismatching_cell(self):
        london = self.geoip_data['London']
        cell_key = {'mnc': 1, 'lac': 1, 'cid': 1}
        cells = [
            dict(mcc=GB_MCC, **cell_key),
            dict(mcc=USA_MCC, **cell_key),
        ]
        # Only add the matching cell to the DB
        self.session.add(Cell(range=1000, radio=Radio.gsm, **cells[0]))
        self.session.flush()

        result = self._make_query(
            data={'cell': [dict(radio=Radio.gsm.name, **cell)
                           for cell in cells]},
            client_addr=london['ip'])
        self.assertEqual(result,
                         {'lat': london['latitude'],
                          'lon': london['longitude'],
                          'accuracy': london['accuracy']})

    def test_cell(self):
        london = self.geoip_data['London']
        cell_key = {'mcc': GB_MCC, 'mnc': 1, 'lac': 1}
        self.session.add(Cell(lat=GB_LAT, lon=GB_LON, range=6000,
                              radio=Radio.gsm, cid=1, **cell_key))
        self.session.add(CellArea(lat=GB_LAT, lon=GB_LON, range=9000,
                                  radio=Radio.gsm, **cell_key))
        self.session.flush()

        result = self._make_query(
            data={'cell': [dict(cid=1, radio=Radio.gsm.name, **cell_key)]},
            client_addr=london['ip'], api_key_log=True)
        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': 6000})

        self.check_stats(
            counter=[
                'm.cell_hit',
                ('m.geoip_hit', 0),
                'm.api_log.test.cell_hit',
                ('m.api_log.test.geoip_hit', 0),
            ],
        )

    def test_ocid_cell(self):
        london = self.geoip_data['London']
        cell_key = {'mcc': GB_MCC, 'mnc': 1, 'lac': 1}
        self.session.add(OCIDCell(lat=GB_LAT, lon=GB_LON, range=6000,
                                  radio=Radio.gsm, cid=1, **cell_key))
        self.session.add(CellArea(lat=GB_LAT, lon=GB_LON, range=9000,
                                  radio=Radio.gsm, **cell_key))
        self.session.flush()

        result = self._make_query(
            data={'cell': [dict(cid=1, radio=Radio.gsm.name, **cell_key)]},
            client_addr=london['ip'], api_key_log=True)
        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': 6000})

    def test_mls_cell_preferred_over_ocid_cell(self):
        london = self.geoip_data['London']
        cell_key = {'mcc': GB_MCC, 'mnc': 1, 'lac': 1}
        self.session.add(Cell(lat=GB_LAT, lon=GB_LON, range=7000,
                              radio=Radio.gsm, cid=1, **cell_key))
        self.session.add(OCIDCell(lat=GB_LAT + 0.001, lon=GB_LON + 0.001,
                                  range=5000, radio=Radio.gsm, cid=1,
                                  **cell_key))
        self.session.add(CellArea(lat=GB_LAT, lon=GB_LON, range=9000,
                                  radio=Radio.gsm, **cell_key))
        self.session.flush()

        result = self._make_query(
            data={'cell': [dict(cid=1, radio=Radio.gsm.name, **cell_key)]},
            client_addr=london['ip'], api_key_log=True)
        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': 7000})

    def test_cell_miss_lac_hit(self):
        lat = PARIS_LAT
        lon = PARIS_LON
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        umts = Radio.umts
        data = [
            Cell(lat=lat, lon=lon, radio=umts, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=umts, cid=5, **key),
            Cell(lat=lat + 0.006, lon=lon + 0.006, radio=umts, cid=6, **key),
            CellArea(lat=lat + 0.0026666, lon=lon + 0.0033333,
                     radio=umts,
                     range=500000, **key),
        ]
        self.session.add_all(data)
        self.session.flush()

        result = self._make_query(
            data={'cell': [dict(radio=Radio.umts.name, cid=7, **key)]},
            api_key_log=True)
        self.assertEqual(result,
                         {'lat': PARIS_LAT + 0.0026666,
                          'lon': PARIS_LON + 0.0033333,
                          'accuracy': 500000})

        self.check_stats(
            counter=[
                'm.cell_lac_hit',
                'm.api_log.test.cell_lac_hit',
                ('m.api_log.test.cell_hit', 0),
                ('m.api_log.test.cell_miss', 0),
            ],
        )

    def test_cell_miss_ocid_lac_hit(self):
        lat = PARIS_LAT
        lon = PARIS_LON
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        umts = Radio.umts
        data = [
            Cell(lat=lat, lon=lon, radio=umts, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=umts, cid=5, **key),
            Cell(lat=lat + 0.006, lon=lon + 0.006, radio=umts, cid=6, **key),
            OCIDCellArea(lat=lat + 0.0026666, lon=lon + 0.0033333,
                         radio=umts,
                         range=500000, **key),
        ]
        self.session.add_all(data)
        self.session.flush()

        result = self._make_query(
            data={'cell': [dict(radio=Radio.umts.name, cid=7, **key)]},
            api_key_log=True)
        self.assertEqual(result,
                         {'lat': PARIS_LAT + 0.0026666,
                          'lon': PARIS_LON + 0.0033333,
                          'accuracy': 500000})

        self.check_stats(
            counter=[
                'm.cell_lac_hit',
                'm.api_log.test.cell_lac_hit',
                ('m.api_log.test.cell_hit', 0),
                ('m.api_log.test.cell_miss', 0),
            ],
        )

    def test_mls_lac_preferred_over_ocid_lac(self):
        lat = PARIS_LAT
        lon = PARIS_LON
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        umts = Radio.umts
        data = [
            Cell(lat=lat, lon=lon, radio=umts, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, radio=umts, cid=5, **key),
            Cell(lat=lat + 0.006, lon=lon + 0.006, radio=umts, cid=6, **key),
            CellArea(lat=lat + 0.0026666, lon=lon + 0.0033333,
                     radio=umts,
                     range=500000, **key),
            OCIDCellArea(lat=lat + 0.0026666, lon=lon + 0.0033333,
                         radio=umts,
                         range=300000, **key),
        ]
        self.session.add_all(data)
        self.session.flush()

        result = self._make_query(
            data={'cell': [dict(radio=Radio.umts.name, cid=7, **key)]},
            api_key_log=True)
        self.assertEqual(result,
                         {'lat': PARIS_LAT + 0.0026666,
                          'lon': PARIS_LON + 0.0033333,
                          'accuracy': 500000})

        self.check_stats(
            counter=[
                'm.cell_lac_hit',
                'm.api_log.test.cell_lac_hit',
                ('m.api_log.test.cell_hit', 0),
                ('m.api_log.test.cell_miss', 0),
            ],
        )

    def test_cell_hit_ignores_lac(self):
        lat = PARIS_LAT
        lon = PARIS_LON
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        data = [
            Cell(lat=lat, lon=lon, range=1000,
                 radio=Radio.umts, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, range=1000,
                 radio=Radio.umts, cid=5, **key),
            Cell(lat=lat + 0.006, lon=lon + 0.006, range=1000,
                 radio=Radio.umts, cid=6, **key),
            CellArea(lat=lat + 0.0026666,
                     lon=lon + 0.0033333, radio=Radio.umts,
                     range=50000, **key),
        ]
        self.session.add_all(data)
        self.session.flush()

        result = self._make_query(
            data={'cell': [dict(radio=Radio.umts.name, cid=5, **key)]})
        self.assertEqual(result,
                         {'lat': PARIS_LAT + 0.002,
                          'lon': PARIS_LON + 0.004,
                          'accuracy': CELL_MIN_ACCURACY})

    def test_lac_miss(self):
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        lat = PARIS_LAT
        lon = PARIS_LON
        data = [
            Cell(lat=lat, lon=lon, radio=Radio.gsm, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004,
                 radio=Radio.gsm, cid=5, **key),
            Cell(lat=1.006, lon=1.006, radio=Radio.gsm, cid=6, **key),
            CellArea(lat=1.0026666, lon=1.0033333, radio=Radio.gsm,
                     range=50000, **key),
        ]
        self.session.add_all(data)
        self.session.flush()

        result = self._make_query(
            data={'cell': [dict(radio=Radio.gsm.name, mcc=FRANCE_MCC,
                                mnc=2, lac=4, cid=5)]})
        self.assertTrue(result is None)

    def test_cell_ignore_invalid_lac_cid(self):
        schema = ValidCellKeySchema()
        lat = PARIS_LAT
        lon = PARIS_LON

        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        ignored_key = dict(
            mcc=FRANCE_MCC, mnc=2,
            lac=schema.fields['lac'].missing,
            cid=schema.fields['cid'].missing)

        data = [
            Cell(lat=lat, lon=lon, range=1000,
                 radio=Radio.gsm, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, range=1000,
                 radio=Radio.gsm, cid=5, **key),
            Cell(lat=lat, lon=lon, range=1000,
                 radio=Radio.gsm, **ignored_key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, range=1000,
                 radio=Radio.lte, **ignored_key),
        ]
        self.session.add_all(data)
        self.session.flush()

        result = self._make_query(data={
            'cell': [
                dict(radio=Radio.gsm.name, cid=4, **key),
                dict(radio=Radio.gsm.name, cid=5, **key),

                dict(radio=Radio.gsm.name, cid=5,
                     mcc=FRANCE_MCC, mnc=2, lac=-1),
                dict(radio=Radio.gsm.name, cid=-1,
                     mcc=FRANCE_MCC, mnc=2, lac=3),
            ]
        })
        self.assertEqual(result,
                         {'lat': PARIS_LAT + 0.001,
                          'lon': PARIS_LON + 0.002,
                          'accuracy': CELL_MIN_ACCURACY})

    def test_cell_multiple_lac_hit(self):
        lat = PARIS_LAT
        lon = PARIS_LON

        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        key2 = dict(mcc=FRANCE_MCC, mnc=2, lac=4)

        expected_lac = CellArea(
            lat=lat + 0.2, lon=lon + 0.2, radio=Radio.gsm,
            range=20000, **key)

        data = [
            Cell(lat=lat + 0.02, lon=lon + 0.02, radio=Radio.gsm,
                 cid=4, range=2000, **key2),
            Cell(lat=lat + 0.04, lon=lon + 0.04, radio=Radio.gsm,
                 cid=5, range=3000, **key2),
            Cell(lat=lat + 0.2, lon=lon + 0.4, radio=Radio.gsm,
                 cid=5, range=1000, **key),
            CellArea(lat=lat, lon=lon, radio=Radio.gsm,
                     range=30000, **key2),
            expected_lac,
        ]
        self.session.add_all(data)
        self.session.flush()

        # We have two lacs, both with two cells, but only know about
        # one cell in one of them and two in the other.
        # The lac with two known cells wins and we use both their
        # positions to calculate the final result.
        result = self._make_query(data={
            'cell': [
                dict(radio=Radio.gsm.name, cid=4, **key),
                dict(radio=Radio.gsm.name, cid=9, **key),
                dict(radio=Radio.gsm.name, cid=4, **key2),
                dict(radio=Radio.gsm.name, cid=5, **key2),
            ]
        })
        self.assertEqual(result,
                         {'lat': expected_lac.lat,
                          'lon': expected_lac.lon,
                          'accuracy': expected_lac.range})

    def test_cell_multiple_lac_lower_range_wins(self):
        lat = PARIS_LAT
        lon = PARIS_LON

        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        key2 = dict(mcc=FRANCE_MCC, mnc=2, lac=4)

        expected_lac = CellArea(
            lat=lat + 0.2, lon=lon + 0.2, radio=Radio.gsm,
            range=10000, **key)

        data = [
            Cell(lat=lat + 0.02, lon=lon + 0.02, radio=Radio.gsm,
                 cid=4, range=2000, **key2),
            Cell(lat=lat + 0.2, lon=lon + 0.4, radio=Radio.gsm,
                 cid=4, range=4000, **key),
            CellArea(lat=lat, lon=lon, radio=Radio.gsm,
                     range=20000, **key2),
            expected_lac,
        ]

        self.session.add_all(data)
        self.session.flush()

        # We have two lacs with each one known cell.
        # The lac with the smallest cell wins.
        result = self._make_query(data={
            'cell': [
                dict(radio=Radio.gsm.name, cid=4, **key),
                dict(radio=Radio.gsm.name, cid=4, **key2),
            ]
        })
        self.assertEqual(result,
                         {'lat': expected_lac.lat,
                          'lon': expected_lac.lon,
                          'accuracy': LAC_MIN_ACCURACY})

    def test_cell_multiple_radio_lac_hit_with_min_lac_accuracy(self):
        lat = PARIS_LAT
        lon = PARIS_LON

        key = dict(mcc=FRANCE_MCC, mnc=3, lac=4)
        key2 = dict(mcc=FRANCE_MCC, mnc=2, lac=3)

        expected_lac = CellArea(
            lat=lat + 0.2, lon=lon + 0.2, radio=Radio.gsm,
            range=3000, **key)

        data = [
            Cell(lat=lat + 0.01, lon=lon + 0.02, radio=Radio.lte,
                 cid=4, range=2000, **key2),
            Cell(lat=lat + 0.2, lon=lon + 0.4, radio=Radio.gsm,
                 cid=5, range=500, **key),
            CellArea(lat=lat, lon=lon, radio=Radio.lte,
                     range=10000, **key2),
            expected_lac,
        ]
        self.session.add_all(data)
        self.session.flush()

        # GSM lac-only hit (cid 9 instead of 5) and a LTE cell hit
        result = self._make_query(data={
            'cell': [
                dict(radio=Radio.gsm.name, cid=9, **key),
                dict(radio=Radio.lte.name, cid=4, **key2),
            ]
        })
        self.assertEqual(result,
                         {'lat': expected_lac.lat,
                          'lon': expected_lac.lon,
                          'accuracy': LAC_MIN_ACCURACY})

    def test_wifi_not_found_cell_fallback(self):
        lat = PARIS_LAT
        lon = PARIS_LON
        key = dict(mcc=FRANCE_MCC, mnc=2, lac=3)
        data = [
            Wifi(key='a0a0a0a0a0a0', lat=3, lon=3),
            Cell(lat=lat, lon=lon, range=1000,
                 radio=Radio.umts, cid=4, **key),
            Cell(lat=lat + 0.002, lon=lon + 0.004, range=1000,
                 radio=Radio.umts, cid=5, **key),
        ]
        self.session.add_all(data)
        self.session.flush()

        result = self._make_query(data={
            'cell': [
                dict(radio=Radio.umts.name, cid=4, **key),
                dict(radio=Radio.umts.name, cid=5, **key),
            ],
            'wifi': [
                {'key': '101010101010'},
                {'key': '202020202020'},
            ],
        })
        self.assertEqual(result,
                         {'lat': PARIS_LAT + 0.001,
                          'lon': PARIS_LON + 0.002,
                          'accuracy': CELL_MIN_ACCURACY})

    def test_cell_multiple_country_codes_from_mcc(self):
        cell_key = {'mcc': GB_MCC, 'mnc': 1, 'lac': 1}
        self.session.add(Cell(lat=GB_LAT, lon=GB_LON, range=6000,
                              radio=Radio.gsm, cid=1, **cell_key))
        self.session.add(CellArea(lat=GB_LAT, lon=GB_LON, range=9000,
                                  radio=Radio.gsm, **cell_key))
        self.session.flush()

        # Without a GeoIP, the mcc results in 4 different equally common
        # mcc values, GB not being the first one. We need to make sure
        # that we accept any of the country codes as a possible match
        # and don't discard otherwise good cell data based on this.
        result = self._make_query(
            data={'cell': [dict(cid=1, radio=Radio.gsm.name, **cell_key)]})
        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON,
                          'accuracy': 6000})

        self.check_stats(
            counter=[
                'm.cell_hit',
            ],
        )

    def test_wifi_disagrees_with_country(self):
        # This test checks that when a wifi is at a lat/lon that
        # is not in the country determined by geoip, we still
        # trust the wifi position over the geoip result

        london = self.geoip_data['London']

        # This lat/lon is Paris, France
        (lat, lon) = (PARIS_LAT, PARIS_LON)

        wifi1 = dict(key='1234567890ab')
        wifi2 = dict(key='1234890ab567')
        wifi3 = dict(key='4321890ab567')
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
        ]
        self.session.add_all(data)
        self.session.flush()

        result = self._make_query(data={'wifi': [wifi1, wifi2, wifi3]},
                                  client_addr=london['ip'])
        self.assertEqual(result,
                         {'lat': PARIS_LAT,
                          'lon': PARIS_LON,
                          'accuracy': WIFI_MIN_ACCURACY})

        self.check_stats(
            counter=[
                ('m.geoip_city_found', 1),
                ('m.geoip_hit', 0),
                ('m.wifi_hit', 1),
            ]
        )

    def test_cell_disagrees_with_lac(self):
        # This test checks that when a cell is at a lat/lon that
        # is not in the LAC associated with it, we drop back
        # to the LAC. This likely represents some kind of internal
        # database consistency error, but it might also just be a
        # new cell that hasn't been integrated yet or something.

        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        data = [
            Cell(lat=PORTO_ALEGRE_LAT,
                 lon=PORTO_ALEGRE_LON,
                 range=1000,
                 radio=Radio.gsm, cid=6789, **key),
            CellArea(lat=SAO_PAULO_LAT,
                     lon=SAO_PAULO_LON,
                     range=10000,
                     radio=Radio.gsm, **key),
        ]
        self.session.add_all(data)
        self.session.flush()

        result = self._make_query(
            data={'cell': [dict(radio=Radio.gsm.name, cid=6789, **key)]})
        self.assertEqual(result,
                         {'lat': SAO_PAULO_LAT,
                          'lon': SAO_PAULO_LON,
                          'accuracy': LAC_MIN_ACCURACY})

        self.check_stats(
            counter=[
                ('m.cell_lac_hit', 1),
            ]
        )

    def test_wifi_disagrees_with_lac(self):
        # This test checks that when a wifi is at a lat/lon that
        # is not in the LAC associated with our query, we drop back
        # to the LAC.

        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        wifi1 = dict(key='1234567890ab')
        wifi2 = dict(key='1234890ab567')
        wifi3 = dict(key='4321890ab567')
        lat = PORTO_ALEGRE_LAT
        lon = PORTO_ALEGRE_LON
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
            CellArea(lat=SAO_PAULO_LAT,
                     lon=SAO_PAULO_LON,
                     range=10000,
                     radio=Radio.gsm, **key),
        ]
        self.session.add_all(data)
        self.session.flush()

        result = self._make_query(data={
            'cell': [dict(radio=Radio.gsm.name, cid=6789, **key)],
            'wifi': [wifi1, wifi2, wifi3],
        })
        self.assertEqual(result,
                         {'lat': SAO_PAULO_LAT,
                          'lon': SAO_PAULO_LON,
                          'accuracy': LAC_MIN_ACCURACY})

        self.check_stats(
            counter=[
                ('m.wifi_hit', 0),
                ('m.cell_lac_hit', 1),
            ]
        )

    def test_wifi_disagrees_with_cell(self):
        # This test checks that when a wifi is at a lat/lon that
        # is not in the cell associated with our query, we drop back
        # to the cell.

        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        wifi1 = dict(key='1234567890ab')
        wifi2 = dict(key='1234890ab567')
        wifi3 = dict(key='4321890ab567')
        lat = PORTO_ALEGRE_LAT
        lon = PORTO_ALEGRE_LON
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 range=1000,
                 radio=Radio.gsm, cid=6789, **key),
        ]
        self.session.add_all(data)
        self.session.flush()

        result = self._make_query(data={
            'cell': [dict(radio=Radio.gsm.name, cid=6789, **key)],
            'wifi': [wifi1, wifi2, wifi3],
        })
        self.assertEqual(result,
                         {'lat': SAO_PAULO_LAT,
                          'lon': SAO_PAULO_LON,
                          'accuracy': CELL_MIN_ACCURACY})

        self.check_stats(
            counter=[
                ('m.wifi_hit', 0),
                ('m.cell_hit', 1),
            ]
        )

    def test_cell_agrees_with_lac(self):
        # This test checks that when a cell is at a lat/lon that
        # is inside its enclosing LAC, we accept it and tighten
        # our accuracy accordingly.

        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        data = [
            Cell(lat=SAO_PAULO_LAT + 0.002,
                 lon=SAO_PAULO_LON + 0.002,
                 range=1000,
                 radio=Radio.gsm, cid=6789, **key),
            CellArea(lat=SAO_PAULO_LAT,
                     lon=SAO_PAULO_LON,
                     range=10000,
                     radio=Radio.gsm, **key),
        ]
        self.session.add_all(data)
        self.session.flush()

        result = self._make_query(data={
            'cell': [dict(radio=Radio.gsm.name, cid=6789, **key)]})
        self.assertEqual(result,
                         {'lat': SAO_PAULO_LAT + 0.002,
                          'lon': SAO_PAULO_LON + 0.002,
                          'accuracy': CELL_MIN_ACCURACY})

        self.check_stats(
            counter=[
                ('m.cell_lac_hit', 0),
                ('m.cell_hit', 1),
            ]
        )

    def test_wifi_agrees_with_cell(self):
        # This test checks that when a wifi is at a lat/lon that
        # is inside its enclosing cell, we accept it and tighten
        # our accuracy accordingly.

        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        wifi1 = dict(key='1234567890ab')
        wifi2 = dict(key='1234890ab567')
        wifi3 = dict(key='4321890ab567')
        lat = SAO_PAULO_LAT + 0.002
        lon = SAO_PAULO_LON + 0.002
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 range=1000,
                 radio=Radio.gsm, cid=6789, **key),
        ]
        self.session.add_all(data)
        self.session.flush()

        result = self._make_query(data={
            'cell': [dict(radio=Radio.gsm.name, cid=6789, **key)],
            'wifi': [wifi1, wifi2, wifi3]})
        self.assertEqual(result,
                         {'lat': SAO_PAULO_LAT + 0.002,
                          'lon': SAO_PAULO_LON + 0.002,
                          'accuracy': WIFI_MIN_ACCURACY})

        self.check_stats(
            counter=[
                ('m.geoip_hit', 0),
                ('m.cell_lac_hit', 0),
                ('m.cell_hit', 0),
                ('m.wifi_hit', 1),
            ]
        )

    def test_wifi_agrees_with_lac(self):
        # This test checks that when a wifi is at a lat/lon that
        # is inside its enclosing LAC, we accept it and tighten
        # our accuracy accordingly.

        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        wifi1 = dict(key='1234567890ab')
        wifi2 = dict(key='1234890ab567')
        wifi3 = dict(key='4321890ab567')
        lat = SAO_PAULO_LAT + 0.002
        lon = SAO_PAULO_LON + 0.002
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
            CellArea(lat=SAO_PAULO_LAT,
                     lon=SAO_PAULO_LON,
                     range=10000,
                     radio=Radio.gsm, **key),
        ]
        self.session.add_all(data)
        self.session.flush()

        result = self._make_query(data={
            'cell': [dict(radio=Radio.gsm.name, cid=6789, **key)],
            'wifi': [wifi1, wifi2, wifi3]})
        self.assertEqual(result,
                         {'lat': SAO_PAULO_LAT + 0.002,
                          'lon': SAO_PAULO_LON + 0.002,
                          'accuracy': WIFI_MIN_ACCURACY})

        self.check_stats(
            counter=[
                ('m.cell_lac_hit', 0),
                ('m.wifi_hit', 1),
            ]
        )

    def test_wifi_agrees_with_cell_and_lac(self):
        # This test checks that when a wifi is at a lat/lon that
        # is inside its enclosing LAC and cell, we accept it and
        # tighten our accuracy accordingly.

        key = dict(mcc=BRAZIL_MCC, mnc=VIVO_MNC, lac=12345)
        wifi1 = dict(key='1234567890ab')
        wifi2 = dict(key='1234890ab567')
        wifi3 = dict(key='4321890ab567')
        lat = SAO_PAULO_LAT + 0.002
        lon = SAO_PAULO_LON + 0.002
        data = [
            Wifi(lat=lat, lon=lon, **wifi1),
            Wifi(lat=lat, lon=lon, **wifi2),
            Wifi(lat=lat, lon=lon, **wifi3),
            Cell(lat=SAO_PAULO_LAT,
                 lon=SAO_PAULO_LON,
                 range=1000,
                 radio=Radio.gsm, cid=6789, **key),
            CellArea(lat=SAO_PAULO_LAT,
                     lon=SAO_PAULO_LON,
                     range=10000,
                     radio=Radio.gsm, **key),
        ]
        self.session.add_all(data)
        self.session.flush()

        result = self._make_query(data={
            'cell': [dict(radio=Radio.gsm.name, cid=6789, **key)],
            'wifi': [wifi1, wifi2, wifi3]})
        self.assertEqual(result,
                         {'lat': SAO_PAULO_LAT + 0.002,
                          'lon': SAO_PAULO_LON + 0.002,
                          'accuracy': WIFI_MIN_ACCURACY})

        self.check_stats(
            counter=[
                ('m.wifi_hit', 1),
            ]
        )

    def test_wifi(self):
        london = self.geoip_data['London']
        wifis = [{'key': '001122334455'}, {'key': '112233445566'}]
        self.session.add(Wifi(
            key=wifis[0]['key'], lat=GB_LAT, lon=GB_LON, range=200))
        self.session.add(Wifi(
            key=wifis[1]['key'], lat=GB_LAT, lon=GB_LON + 0.00001, range=300))
        self.session.flush()

        result = self._make_query(
            data={'wifi': wifis}, client_addr=london['ip'], api_key_log=True)
        self.assertEqual(result,
                         {'lat': GB_LAT,
                          'lon': GB_LON + 0.000005,
                          'accuracy': WIFI_MIN_ACCURACY})

        self.check_stats(
            counter=[
                'm.wifi_hit',
                'm.api_log.test.wifi_hit',
            ],
            timer=[
                'm.wifi.provided',
            ],
        )

    def test_wifi_too_few_candidates(self):
        wifis = [
            Wifi(key='001122334455', lat=1.0, lon=1.0),
            Wifi(key='112233445566', lat=1.001, lon=1.002),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        result = self._make_query(
            data={'wifi': [{'key': '001122334455'}]}, api_key_log=True)
        self.assertTrue(result is None)
        self.check_stats(
            counter=[
                'm.miss',
                'm.wifi.provided_too_few',
                'm.api_log.test.geoip_miss',
                ('m.api_log.test.wifi_miss', 0),
            ],
        )

    def test_wifi_too_few_matches(self):
        wifis = [
            Wifi(key='001122334455', lat=1.0, lon=1.0),
            Wifi(key='112233445566', lat=1.001, lon=1.002),
            Wifi(key='223344556677', lat=None, lon=None),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        result = self._make_query(
            data={'wifi': [{'key': '001122334455'}, {'key': '223344556677'}]})
        self.assertTrue(result is None)
        self.check_stats(
            counter=[
                'm.miss',
                'm.wifi.found_too_few',
                'm.wifi.partial_match',
            ],
            timer=[
                'm.wifi.provided_not_known',
            ],
        )

    def test_wifi_too_similar_bssids_by_arithmetic_difference(self):
        wifis = [
            Wifi(key='00000000001f', lat=1.0, lon=1.0),
            Wifi(key='000000000020', lat=1.0, lon=1.0),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        result = self._make_query(
            data={'wifi': [{'key': '00000000001f'},
                           {'key': '000000000020'}]},
            api_key_log=True)
        self.assertTrue(result is None)
        self.check_stats(
            counter=[
                'm.miss',
                'm.api_log.test.geoip_miss',
            ],
            timer=[
                'm.wifi.provided_too_similar',
            ],
        )

    def test_wifi_too_similar_bssids_by_hamming_distance(self):
        wifis = [
            Wifi(key='000000000058', lat=1.0, lon=1.0),
            Wifi(key='00000000005c', lat=1.0, lon=1.0),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        result = self._make_query(
            data={'wifi': [{'key': '000000000058'},
                           {'key': '00000000005c'}]},
            api_key_log=True)
        self.assertTrue(result is None)
        self.check_stats(
            counter=[
                'm.miss',
                'm.api_log.test.geoip_miss',
            ],
            timer=[
                'm.wifi.provided_too_similar',
            ],
        )

    def test_wifi_similar_bssids_but_enough_clusters(self):
        wifis = [
            Wifi(key='00000000001f', lat=1.0, lon=1.0),
            Wifi(key='000000000020', lat=1.0, lon=1.0),
            Wifi(key='000000000058', lat=1.00004, lon=1.00004),
            Wifi(key='00000000005c', lat=1.00004, lon=1.00004),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        result = self._make_query(
            data={'wifi': [{'key': '00000000001f'},
                           {'key': '000000000020'},
                           {'key': '000000000058'},
                           {'key': '00000000005c'}]})
        self.assertEqual(result,
                         {'lat': 1.00002,
                          'lon': 1.00002,
                          'accuracy': 100.0})

    def test_wifi_similar_bssids_but_enough_found_clusters(self):
        wifis = [
            Wifi(key='00000000001f', lat=1.0, lon=1.0),
            Wifi(key='000000000024', lat=1.00004, lon=1.00004),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        result = self._make_query(
            data={'wifi': [{'key': '00000000001f'},
                           {'key': '000000000020'},
                           {'key': '000000000021'},
                           {'key': '000000000022'},
                           {'key': '000000000023'},
                           {'key': '000000000024'}]})
        self.assertEqual(result,
                         {'lat': 1.00002,
                          'lon': 1.00002,
                          'accuracy': 100.0})

    def test_wifi_ignore_outlier(self):
        wifis = [
            Wifi(key='001122334455', lat=1.0, lon=1.0),
            Wifi(key='112233445566', lat=1.001, lon=1.002),
            Wifi(key='223344556677', lat=1.002, lon=1.004),
            Wifi(key='334455667788', lat=2.0, lon=2.0),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        result = self._make_query(data={
            'wifi': [
                {'key': '001122334455'}, {'key': '112233445566'},
                {'key': '223344556677'}, {'key': '334455667788'},
            ]})
        self.assertEqual(result,
                         {'lat': 1.001,
                          'lon': 1.002,
                          'accuracy': 248.6090897})

    def test_wifi_prefer_cluster_with_better_signals(self):
        wifis = [
            Wifi(key='a1' * 6, lat=1.0, lon=1.0),
            Wifi(key='b2' * 6, lat=1.001, lon=1.002),
            Wifi(key='c3' * 6, lat=1.002, lon=1.004),
            Wifi(key='d4' * 6, lat=2.0, lon=2.0),
            Wifi(key='e5' * 6, lat=2.001, lon=2.002),
            Wifi(key='f6' * 6, lat=2.002, lon=2.004),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        result = self._make_query(data={
            'wifi': [
                {'key': 'A1' * 6, 'signal': -100},
                {'key': 'D4' * 6, 'signal': -80},
                {'key': 'B2' * 6, 'signal': -100},
                {'key': 'E5' * 6, 'signal': -90},
                {'key': 'C3' * 6, 'signal': -100},
                {'key': 'F6' * 6, 'signal': -54},
            ]})
        self.assertEqual(result,
                         {'lat': 2.001,
                          'lon': 2.002,
                          'accuracy': 248.51819})

    def test_wifi_prefer_larger_cluster_over_high_signal(self):
        wifis = [Wifi(key=('0%X' % i).lower() * 6,
                      lat=1 + i * 0.000010,
                      lon=1 + i * 0.000012)
                 for i in range(1, 6)]
        wifis += [
            Wifi(key='d4' * 6, lat=2.0, lon=2.0),
            Wifi(key='e5' * 6, lat=2.001, lon=2.002),
            Wifi(key='f6' * 6, lat=2.002, lon=2.004),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        observations = [dict(key=('0%X' % i) * 6,
                             signal=-80)
                        for i in range(1, 6)]
        observations += [
            dict(key='D4' * 6, signal=-75),
            dict(key='E5' * 6, signal=-74),
            dict(key='F6' * 6, signal=-73)
        ]
        random.shuffle(observations)

        result = self._make_query(data={'wifi': observations})
        self.assertEqual(result,
                         {'lat': 1.00003,
                          'lon': 1.000036,
                          'accuracy': WIFI_MIN_ACCURACY})

    def test_wifi_only_use_top_five_signals_in_noisy_cluster(self):
        # all these should wind up in the same cluster since
        # clustering threshold is 500m and the 10 wifis are
        # spaced in increments of (+1m, +1.2m)
        wifis = [Wifi(key=('0%X'.lower() % i) * 6,
                      lat=1 + i * 0.000010,
                      lon=1 + i * 0.000012)
                 for i in range(1, 11)]
        self.session.add_all(wifis)
        self.session.commit()
        observations = [dict(key=('0%X' % i) * 6,
                             signal=-80)
                        for i in range(6, 11)]
        observations += [
            dict(key='010101010101', signal=-75),
            dict(key='020202020202', signal=-74),
            dict(key='030303030303', signal=-73),
            dict(key='040404040404', signal=-72),
            dict(key='050505050505', signal=-71),
        ]
        random.shuffle(observations)

        result = self._make_query(data={'wifi': observations})
        self.assertEqual(result,
                         {'lat': 1.00003,
                          'lon': 1.000036,
                          'accuracy': WIFI_MIN_ACCURACY})

    def test_wifi_not_closeby(self):
        wifis = [
            Wifi(key='101010101010', lat=1.0, lon=1.0),
            Wifi(key='202020202020', lat=1.001, lon=1.002),
            Wifi(key='303030303030', lat=2.002, lon=2.004),
            Wifi(key='404040404040', lat=2.0, lon=2.0),
        ]
        self.session.add_all(wifis)
        self.session.flush()

        result = self._make_query(
            data={'wifi': [{'key': '101010101010'}, {'key': '303030303030'}]},
            api_key_log=True)
        self.assertTrue(result is None)
        self.check_stats(
            counter=[
                'm.miss',
                'm.api_log.test.wifi_miss',
            ],
        )


class TestCountrySearcher(BaseLocateTest):

    searcher = locate.CountrySearcher

    def test_country_geoip(self):
        bhutan = self.geoip_data['Bhutan']
        result = self._make_query(client_addr=bhutan['ip'], api_key_log=True)
        self.assertEqual(result,
                         {'country_code': bhutan['country_code'],
                          'country_name': bhutan['country_name']})

        self.check_stats(
            counter=[
                'm.geoip_country_found',
                'm.geoip_hit',
                'm.api_log.test.geoip_hit',
            ],
        )

    def test_country_geoip_unknown(self):
        result = self._make_query(client_addr='127.0.0.1')
        self.assertTrue(result is None)

    def test_no_wifi_provider(self):
        london = self.geoip_data['London']
        wifis = [{'key': '001122334455'}, {'key': '112233445566'}]
        self.session.add(Wifi(
            key=wifis[0]['key'], lat=GB_LAT, lon=GB_LON, range=200))
        self.session.add(Wifi(
            key=wifis[1]['key'], lat=GB_LAT, lon=GB_LON + 0.00001, range=300))
        self.session.flush()

        with self.db_call_checker() as check_db_calls:
            result = self._make_query(
                data={'wifi': wifis}, client_addr=london['ip'])
            check_db_calls(rw=0, ro=0)

        self.assertEqual(result,
                         {'country_code': london['country_code'],
                          'country_name': london['country_name']})

    def test_mcc_without_geoip(self):
        bhutan = self.geoip_data['Bhutan']
        cell_key = {
            'radio': Radio.gsm.name, 'mcc': BHUTAN_MCC, 'mnc': 1, 'lac': 1}

        with self.db_call_checker() as check_db_calls:
            result = self._make_query(data={'cell': [dict(cid=1, **cell_key)]},
                                      client_addr='127.0.0.1')
            check_db_calls(rw=0, ro=0)

        self.assertEqual(result,
                         {'country_code': bhutan['country_code'],
                          'country_name': bhutan['country_name']})

    def test_prefer_mcc_over_geoip(self):
        bhutan = self.geoip_data['Bhutan']
        london = self.geoip_data['London']
        cell_key = {
            'radio': Radio.gsm.name, 'mcc': BHUTAN_MCC, 'mnc': 1, 'lac': 1}

        with self.db_call_checker() as check_db_calls:
            result = self._make_query(data={'cell': [dict(cid=1, **cell_key)]},
                                      client_addr=london['ip'])
            check_db_calls(rw=0, ro=0)

        self.assertEqual(result,
                         {'country_code': bhutan['country_code'],
                          'country_name': bhutan['country_name']})

    def test_refuse_guessing_multiple_cell_countries(self):
        bhutan = self.geoip_data['Bhutan']
        cell_key = {
            'radio': Radio.gsm.name, 'mcc': GB_MCC, 'mnc': 1, 'lac': 1}

        with self.db_call_checker() as check_db_calls:
            result = self._make_query(data={'cell': [dict(cid=1, **cell_key)]},
                                      client_addr=bhutan['ip'])
            check_db_calls(rw=0, ro=0)

        self.assertEqual(result,
                         {'country_code': bhutan['country_code'],
                          'country_name': bhutan['country_name']})

    def test_neither_mcc_nor_geoip(self):
        cell_key = {
            'radio': Radio.gsm.name, 'mcc': GB_MCC, 'mnc': 1, 'lac': 1}

        with self.db_call_checker() as check_db_calls:
            result = self._make_query(data={'cell': [dict(cid=1, **cell_key)]},
                                      client_addr='127.0.0.1')
            check_db_calls(rw=0, ro=0)

        self.assertTrue(result is None)
